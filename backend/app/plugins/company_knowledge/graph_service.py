"""文档级关系图谱服务（B1/B4）：关系 CRUD、图谱数据组装与检索扩展查询。

- 关系状态：draft(待确认) / confirmed(已确认，参与检索) / rejected(已拒绝)。
- 来源：llm(大模型抽取) / manual(人工维护) / system(系统规则，如版本替代)。
- 图谱节点口径：已发布且生效、access_scope 允许的文档；system 替代边由
  `company_knowledge_sources.replaced_source_id` 实时并入，不落关系表。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge import (
    CompanyKnowledgeJob,
    CompanyKnowledgeRelation,
    CompanyKnowledgeSource,
)
from app.plugins.company_knowledge.graph_extractor import extract_relations_from_text

RELATION_TYPES = ("cite", "supersede", "parent", "related")
RELATION_TYPE_LABELS = {"cite": "引用", "supersede": "替代", "parent": "上下位", "related": "关联"}
RELATION_STATUSES = ("draft", "confirmed", "rejected")
RELATION_ORIGINS = ("llm", "manual", "system")
DIRECTIONS = ("directed", "undirected")
GRAPH_EXTRACTION_JOB_TYPE = "graph_extract"
ACTIVE_JOB_STATUSES = ("queued", "running")


class GraphServiceError(RuntimeError):
    pass


def graph_extraction_job_to_dict(
    job: CompanyKnowledgeJob,
    *,
    source_title: str | None = None,
) -> dict:
    """序列化图谱关系抽取任务，供管理端展示任务状态与结果摘要。"""
    snapshot = job.request_snapshot if isinstance(job.request_snapshot, dict) else {}
    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    return {
        "id": str(job.id),
        "source_id": str(job.source_id) if job.source_id else None,
        "source_title": source_title or "已删除资料",
        "status": job.status,
        "trigger": snapshot.get("trigger") or "",
        "result": {
            "created": result.get("created", 0),
            "skipped": result.get("skipped", 0),
            "unmatched_count": result.get("unmatched_count", 0),
        },
        "error_message": job.error_message or "",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


async def list_graph_relation_extraction_jobs(
    db: AsyncSession,
    *,
    limit: int = 12,
) -> list[dict]:
    """返回最近的图谱关系抽取任务，包含资料标题和生成结果摘要。"""
    rows = await db.execute(
        select(CompanyKnowledgeJob, CompanyKnowledgeSource.title)
        .outerjoin(CompanyKnowledgeSource, CompanyKnowledgeSource.id == CompanyKnowledgeJob.source_id)
        .where(CompanyKnowledgeJob.job_type == GRAPH_EXTRACTION_JOB_TYPE)
        .order_by(CompanyKnowledgeJob.created_at.desc())
        .limit(limit)
    )
    return [
        graph_extraction_job_to_dict(job, source_title=source_title)
        for job, source_title in rows.all()
    ]


async def enqueue_graph_relation_extraction(
    db: AsyncSession,
    *,
    source_id: str,
    admin_id,
    trigger: str,
    force: bool = False,
) -> tuple[CompanyKnowledgeJob, bool]:
    """为一份已发布资料创建关系草稿抽取任务。

    同一资料在已有排队或运行中的抽取任务时复用任务，避免发布重试或重复点击
    造成并发模型调用。任务只会创建 draft 关系，仍须管理员确认才能参与检索。
    """
    try:
        source_uuid = uuid.UUID(str(source_id))
    except (TypeError, ValueError) as exc:
        raise GraphServiceError("资料标识不合法") from exc

    source = await db.get(CompanyKnowledgeSource, source_uuid)
    if not source:
        raise GraphServiceError("资料不存在")
    if source.status != "published":
        raise GraphServiceError("只有已发布资料可以生成关系草稿")

    active_result = await db.execute(
        select(CompanyKnowledgeJob)
        .where(
            CompanyKnowledgeJob.source_id == source.id,
            CompanyKnowledgeJob.job_type == GRAPH_EXTRACTION_JOB_TYPE,
            CompanyKnowledgeJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(CompanyKnowledgeJob.created_at.desc())
        .limit(1)
    )
    active_job = active_result.scalar_one_or_none()
    if active_job:
        return active_job, False

    if not force:
        completed_result = await db.execute(
            select(CompanyKnowledgeJob)
            .where(
                CompanyKnowledgeJob.source_id == source.id,
                CompanyKnowledgeJob.job_type == GRAPH_EXTRACTION_JOB_TYPE,
                CompanyKnowledgeJob.status == "succeeded",
            )
            .order_by(CompanyKnowledgeJob.finished_at.desc())
            .limit(1)
        )
        completed_job = completed_result.scalar_one_or_none()
        if (
            completed_job
            and completed_job.finished_at
            and source.published_at
            and completed_job.finished_at >= source.published_at
        ):
            return completed_job, False

    job = CompanyKnowledgeJob(
        source_id=source.id,
        job_type=GRAPH_EXTRACTION_JOB_TYPE,
        status="queued",
        requested_by=admin_id,
        total_chunks=1,
        request_snapshot={"trigger": trigger},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job, True


async def enqueue_graph_relation_extractions_for_published_sources(
    db: AsyncSession,
    *,
    admin_id,
) -> tuple[list[CompanyKnowledgeJob], int]:
    """为图谱口径内的存量资料批量创建关系草稿任务。

    只扫描已发布、生效且允许全员访问的资料，与图谱节点和关系候选的口径一致。
    """
    now = datetime.now(timezone.utc)
    sources_result = await db.execute(
        select(CompanyKnowledgeSource).where(
            CompanyKnowledgeSource.status == "published",
            CompanyKnowledgeSource.access_scope == "all_users",
            CompanyKnowledgeSource.effective_at <= now,
            or_(
                CompanyKnowledgeSource.expires_at.is_(None),
                CompanyKnowledgeSource.expires_at > now,
            ),
        )
    )
    sources = list(sources_result.scalars().all())
    if not sources:
        return [], 0

    source_ids = [source.id for source in sources]
    active_result = await db.execute(
        select(CompanyKnowledgeJob).where(
            CompanyKnowledgeJob.source_id.in_(source_ids),
            CompanyKnowledgeJob.job_type == GRAPH_EXTRACTION_JOB_TYPE,
            CompanyKnowledgeJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    )
    active_jobs = list(active_result.scalars().all())
    active_source_ids = {job.source_id for job in active_jobs}
    queued_jobs = [job for job in active_jobs if job.status == "queued"]
    completed_result = await db.execute(
        select(CompanyKnowledgeJob.source_id, func.max(CompanyKnowledgeJob.finished_at))
        .where(
            CompanyKnowledgeJob.source_id.in_(source_ids),
            CompanyKnowledgeJob.job_type == GRAPH_EXTRACTION_JOB_TYPE,
            CompanyKnowledgeJob.status == "succeeded",
        )
        .group_by(CompanyKnowledgeJob.source_id)
    )
    completed_at_by_source = {row[0]: row[1] for row in completed_result.all()}
    already_scanned_source_ids = {
        source.id
        for source in sources
        if completed_at_by_source.get(source.id)
        and source.published_at
        and completed_at_by_source[source.id] >= source.published_at
    }
    running_source_ids = {job.source_id for job in active_jobs if job.status == "running"}
    skipped_source_ids = running_source_ids | already_scanned_source_ids
    queued_sources = [
        source
        for source in sources
        if source.id not in (active_source_ids | already_scanned_source_ids)
    ]
    if not queued_sources:
        return queued_jobs, len(skipped_source_ids)

    jobs = [
        CompanyKnowledgeJob(
            source_id=source.id,
            job_type=GRAPH_EXTRACTION_JOB_TYPE,
            status="queued",
            requested_by=admin_id,
            total_chunks=1,
            request_snapshot={"trigger": "batch_backfill"},
        )
        for source in queued_sources
    ]
    db.add_all(jobs)
    await db.commit()
    for job in jobs:
        await db.refresh(job)
    return [*queued_jobs, *jobs], len(skipped_source_ids)


async def execute_graph_relation_extraction_job(
    db: AsyncSession,
    *,
    job_id: str,
) -> CompanyKnowledgeJob | None:
    """在独立数据库会话内运行一个已入队的关系草稿抽取任务。"""
    try:
        job_uuid = uuid.UUID(str(job_id))
    except (TypeError, ValueError):
        return None

    job = await db.get(CompanyKnowledgeJob, job_uuid)
    if not job or job.job_type != GRAPH_EXTRACTION_JOB_TYPE:
        return None
    if job.status != "queued":
        return job

    source = await db.get(CompanyKnowledgeSource, job.source_id)
    if not source or source.status != "published":
        job.status = "cancelled"
        job.error_message = "资料已下架或删除，未执行关系草稿抽取"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return job

    started_at = datetime.now(timezone.utc)
    claim_result = await db.execute(
        update(CompanyKnowledgeJob)
        .where(
            CompanyKnowledgeJob.id == job_uuid,
            CompanyKnowledgeJob.status == "queued",
        )
        .values(status="running", started_at=started_at, error_message="")
        .returning(CompanyKnowledgeJob.id)
    )
    if not claim_result.scalar_one_or_none():
        await db.rollback()
        return await db.get(CompanyKnowledgeJob, job_uuid)

    job.status = "running"
    job.started_at = started_at
    job.error_message = ""
    await db.commit()

    try:
        result = await extract_source_relations(
            db,
            source_id=str(source.id),
            admin_id=job.requested_by,
        )
        snapshot = dict(job.request_snapshot or {})
        snapshot["result"] = {
            "created": result["created"],
            "skipped": result["skipped"],
            "unmatched_count": len(result["unmatched"]),
        }
        job.request_snapshot = snapshot
        job.status = "succeeded"
        job.succeeded_chunks = 1
        job.failed_chunks = 0
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return job
    except Exception as exc:
        await db.rollback()
        failed_job = await db.get(CompanyKnowledgeJob, job_uuid)
        if not failed_job:
            return None
        failed_job.status = "failed"
        failed_job.failed_chunks = 1
        failed_job.error_message = str(exc)[:2000]
        failed_job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return failed_job


def relation_to_dict(relation: CompanyKnowledgeRelation) -> dict:
    return {
        "id": str(relation.id),
        "source_id": str(relation.source_id),
        "target_source_id": str(relation.target_source_id),
        "relation_type": relation.relation_type,
        "relation_label": RELATION_TYPE_LABELS.get(relation.relation_type, relation.relation_type),
        "direction": relation.direction,
        "evidence": relation.evidence,
        "origin": relation.origin,
        "status": relation.status,
        "created_by": str(relation.created_by),
        "confirmed_by": str(relation.confirmed_by) if relation.confirmed_by else None,
        "created_at": relation.created_at.isoformat() if relation.created_at else None,
        "confirmed_at": relation.confirmed_at.isoformat() if relation.confirmed_at else None,
    }


def _system_supersede_edge(source: CompanyKnowledgeSource) -> dict | None:
    """把 replaced_source_id 表达为 system 来源的 supersede 边（旧版 → 新版）。"""
    if not source.replaced_source_id:
        return None
    return {
        "id": f"system-supersede-{source.id}",
        "source_id": str(source.replaced_source_id),
        "target_source_id": str(source.id),
        "relation_type": "supersede",
        "relation_label": "替代",
        "direction": "directed",
        "evidence": "系统规则：版本替代（replaced_source_id）",
        "origin": "system",
        "status": "confirmed",
        "created_by": "",
        "confirmed_by": "",
        "created_at": None,
        "confirmed_at": None,
    }


def validate_relation_input(
    *,
    source_id: str,
    target_source_id: str,
    relation_type: str,
    direction: str = "undirected",
    origin: str = "manual",
) -> None:
    if not source_id or not target_source_id:
        raise GraphServiceError("源文档与目标文档均必填")
    if str(source_id) == str(target_source_id):
        raise GraphServiceError("源文档与目标文档不能相同")
    if relation_type not in RELATION_TYPES:
        raise GraphServiceError(f"不支持的关系类型：{relation_type}")
    if direction not in DIRECTIONS:
        raise GraphServiceError(f"不支持的方向类型：{direction}")
    if origin not in RELATION_ORIGINS:
        raise GraphServiceError(f"不支持的关系来源：{origin}")


async def create_relation(
    db: AsyncSession,
    *,
    source_id: str,
    target_source_id: str,
    relation_type: str,
    direction: str = "undirected",
    evidence: str = "",
    origin: str = "manual",
    admin_id,
) -> CompanyKnowledgeRelation:
    validate_relation_input(
        source_id=source_id,
        target_source_id=target_source_id,
        relation_type=relation_type,
        direction=direction,
        origin=origin,
    )
    source_uuid = uuid.UUID(str(source_id))
    target_uuid = uuid.UUID(str(target_source_id))
    rows = await db.execute(
        select(CompanyKnowledgeSource.id).where(
            CompanyKnowledgeSource.id.in_([source_uuid, target_uuid])
        )
    )
    found = {row[0] for row in rows.all()}
    missing = {source_uuid, target_uuid} - found
    if missing:
        raise GraphServiceError("源文档或目标文档不存在")

    relation = CompanyKnowledgeRelation(
        source_id=source_uuid,
        target_source_id=target_uuid,
        relation_type=relation_type,
        direction=direction,
        evidence=(evidence or "").strip(),
        origin=origin,
        status="draft",
        created_by=admin_id,
    )
    db.add(relation)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise GraphServiceError("该关系已存在（相同两端与类型）") from exc
    await db.refresh(relation)
    return relation


async def update_relation_status(
    db: AsyncSession,
    *,
    relation_id: str,
    status: str,
    admin_id,
) -> CompanyKnowledgeRelation:
    if status not in RELATION_STATUSES:
        raise GraphServiceError(f"不支持的关系状态：{status}")
    relation = await db.get(CompanyKnowledgeRelation, uuid.UUID(str(relation_id)))
    if not relation:
        raise GraphServiceError("关系不存在")
    relation.status = status
    relation.confirmed_by = admin_id
    relation.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(relation)
    return relation


async def delete_relation(db: AsyncSession, *, relation_id: str) -> None:
    relation = await db.get(CompanyKnowledgeRelation, uuid.UUID(str(relation_id)))
    if not relation:
        raise GraphServiceError("关系不存在")
    await db.delete(relation)
    await db.commit()


async def list_relations(
    db: AsyncSession,
    *,
    source_id: str | None = None,
    status: str | None = None,
    limit: int = 500,
) -> list[CompanyKnowledgeRelation]:
    query = select(CompanyKnowledgeRelation).order_by(CompanyKnowledgeRelation.created_at.desc())
    if source_id:
        source_uuid = uuid.UUID(str(source_id))
        query = query.where(
            or_(
                CompanyKnowledgeRelation.source_id == source_uuid,
                CompanyKnowledgeRelation.target_source_id == source_uuid,
            )
        )
    if status:
        query = query.where(CompanyKnowledgeRelation.status == status)
    query = query.limit(limit)
    rows = await db.execute(query)
    return list(rows.scalars().all())


async def build_graph(
    db: AsyncSession,
    *,
    include_system_edges: bool = True,
) -> dict:
    """组装图谱数据：nodes = 已发布生效文档；edges = 关系（含 system 替代边）。

    待确认(draft)关系也会返回（前端高亮提示确认），检索仅使用 confirmed。
    """
    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(CompanyKnowledgeSource)
        .where(
            CompanyKnowledgeSource.status == "published",
            CompanyKnowledgeSource.access_scope == "all_users",
            CompanyKnowledgeSource.effective_at <= now,
            or_(
                CompanyKnowledgeSource.expires_at.is_(None),
                CompanyKnowledgeSource.expires_at > now,
            ),
        )
        .order_by(CompanyKnowledgeSource.title.asc())
    )
    sources = rows.scalars().all()
    node_ids = {source.id for source in sources}
    node_by_id = {source.id: source for source in sources}

    nodes = [
        {
            "id": str(source.id),
            "title": source.title,
            "knowledge_type": source.knowledge_type,
            "category": source.category,
            "version": source.version,
            "effective_at": source.effective_at.date().isoformat() if source.effective_at else None,
        }
        for source in sources
    ]

    edges = []
    relation_rows = await db.execute(
        select(CompanyKnowledgeRelation).order_by(CompanyKnowledgeRelation.created_at.desc())
    )
    for relation in relation_rows.scalars().all():
        if relation.source_id in node_ids and relation.target_source_id in node_ids:
            edges.append(relation_to_dict(relation))

    if include_system_edges:
        for source in sources:
            edge = _system_supersede_edge(source)
            if edge and uuid.UUID(edge["source_id"]) in node_ids:
                edges.append(edge)

    return {"nodes": nodes, "edges": edges}


async def get_confirmed_relations(
    db: AsyncSession,
    source_ids: list[str],
) -> list[dict]:
    """B4：取一组源文档的 1 跳已确认关系（含方向相反的边）。"""
    if not source_ids:
        return []
    uuids = []
    for raw in source_ids:
        try:
            uuids.append(uuid.UUID(str(raw)))
        except (ValueError, TypeError):
            continue
    if not uuids:
        return []
    rows = await db.execute(
        select(CompanyKnowledgeRelation).where(
            CompanyKnowledgeRelation.status == "confirmed",
            or_(
                CompanyKnowledgeRelation.source_id.in_(uuids),
                CompanyKnowledgeRelation.target_source_id.in_(uuids),
            ),
        )
    )
    return [relation_to_dict(relation) for relation in rows.scalars().all()]


async def extract_source_relations(
    db: AsyncSession,
    *,
    source_id: str,
    admin_id,
) -> dict:
    """B2：对已发布资料做 LLM 关系抽取，结果进草稿态。

    返回 {"created": n, "skipped": n, "unmatched": [条目]}。
    """
    source = await db.get(CompanyKnowledgeSource, uuid.UUID(str(source_id)))
    if not source:
        raise GraphServiceError("资料不存在")
    if source.status != "published":
        raise GraphServiceError("只有已发布资料可以抽取关系")

    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(CompanyKnowledgeSource).where(
            CompanyKnowledgeSource.status == "published",
            CompanyKnowledgeSource.access_scope == "all_users",
            CompanyKnowledgeSource.effective_at <= now,
            or_(
                CompanyKnowledgeSource.expires_at.is_(None),
                CompanyKnowledgeSource.expires_at > now,
            ),
        )
    )
    known_titles = [
        {"id": item.id, "title": item.title}
        for item in rows.scalars().all()
        if item.id != source.id
    ]

    text = source.preprocessed_content or source.markdown_content or source.raw_content
    try:
        matched, unmatched = await extract_relations_from_text(
            text,
            source_title=source.title,
            known_titles=known_titles,
        )
    except Exception as exc:
        raise GraphServiceError(f"关系抽取失败：{exc}") from exc

    created = 0
    skipped = 0
    for item in matched:
        try:
            await create_relation(
                db,
                source_id=str(source.id),
                target_source_id=item["target_source_id"],
                relation_type=item["relation_type"],
                evidence=item["evidence"],
                origin="llm",
                admin_id=admin_id,
            )
            created += 1
        except GraphServiceError:
            skipped += 1
    return {"created": created, "skipped": skipped, "unmatched": unmatched}
