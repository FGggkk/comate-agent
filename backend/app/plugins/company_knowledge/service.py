"""公司资料导入、发布、版本替换与会话写入服务。"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge import (
    CompanyKnowledgeChunk,
    CompanyKnowledgeChunkSet,
    CompanyKnowledgeJob,
    CompanyKnowledgeSource,
)
from app.models.conversation import Message, Session
from app.plugins.company_knowledge.chunker import chunk_text
from app.plugins.company_knowledge.importer import SourceImportError, content_hash, read_text_source, to_markdown
from app.plugins.company_knowledge.memory_boundary import COMPANY_KNOWLEDGE_MESSAGE_TYPE
from app.plugins.company_knowledge.registry import get_knowledge_type, is_import_enabled
from app.services.embedding_service import get_embeddings_batch


EMBEDDING_BATCH_SIZE = 16


class CompanyKnowledgeServiceError(RuntimeError):
    pass


def source_to_dict(source: CompanyKnowledgeSource) -> dict:
    return {
        "id": str(source.id),
        "title": source.title,
        "knowledge_type": source.knowledge_type,
        "category": source.category or "",
        "source_format": source.source_format,
        "file_name": source.file_name,
        "version": source.version,
        "effective_at": _format_datetime(source.effective_at),
        "expires_at": _format_datetime(source.expires_at),
        "status": source.status,
        "access_scope": source.access_scope,
        "content_hash": source.content_hash,
        "markdown_version": source.markdown_version,
        "conversion_warnings": source.conversion_warnings or [],
        "active_chunk_set_id": str(source.active_chunk_set_id) if source.active_chunk_set_id else None,
        "created_at": _format_datetime(source.created_at),
        "updated_at": _format_datetime(source.updated_at),
        "published_at": _format_datetime(source.published_at),
        "chunk_count": getattr(source, "chunk_count", None),
        "error_message": getattr(source, "error_message", None),
    }


def chunk_set_to_dict(chunk_set: CompanyKnowledgeChunkSet) -> dict:
    return {
        "id": str(chunk_set.id),
        "source_id": str(chunk_set.source_id),
        "markdown_version": chunk_set.markdown_version,
        "mode": chunk_set.mode,
        "status": chunk_set.status,
        "rule_snapshot": chunk_set.rule_snapshot or {},
        "total_chunks": chunk_set.total_chunks,
        "indexed_chunks": chunk_set.indexed_chunks,
        "error_message": chunk_set.error_message or "",
        "created_at": _format_datetime(chunk_set.created_at),
        "confirmed_at": _format_datetime(chunk_set.confirmed_at),
        "indexed_at": _format_datetime(chunk_set.indexed_at),
        "validated_at": _format_datetime(chunk_set.validated_at),
    }


def chunk_to_dict(chunk: CompanyKnowledgeChunk) -> dict:
    return {
        "id": str(chunk.id),
        "chunk_index": chunk.chunk_index,
        "section_path": chunk.section_path or "",
        "content": chunk.content,
        "token_count": chunk.token_count,
        "status": chunk.status,
    }


def job_to_dict(job: CompanyKnowledgeJob) -> dict:
    return {
        "id": str(job.id),
        "source_id": str(job.source_id) if job.source_id else None,
        "chunk_set_id": str(job.chunk_set_id) if job.chunk_set_id else None,
        "job_type": job.job_type,
        "status": job.status,
        "total_chunks": job.total_chunks,
        "succeeded_chunks": job.succeeded_chunks,
        "failed_chunks": job.failed_chunks,
        "error_message": job.error_message or "",
        "created_at": _format_datetime(job.created_at),
        "started_at": _format_datetime(job.started_at),
        "finished_at": _format_datetime(job.finished_at),
    }


async def import_company_source(
    db: AsyncSession,
    *,
    file_name: str,
    file_content: bytes,
    title: str,
    version: str,
    knowledge_type: str,
    effective_at: datetime,
    expires_at: datetime | None,
    category: str,
    metadata: dict | None,
    admin_id,
) -> CompanyKnowledgeSource:
    _ensure_import_enabled(knowledge_type)
    imported = read_text_source(file_name, file_content)
    normalized_title = title.strip()
    normalized_version = version.strip()
    if not normalized_title or not normalized_version:
        raise SourceImportError("制度名称和版本号不能为空")
    if expires_at and _as_utc(expires_at) <= _as_utc(effective_at):
        raise SourceImportError("失效时间必须晚于生效时间")

    existing = await db.execute(
        select(CompanyKnowledgeSource).where(
            CompanyKnowledgeSource.title == normalized_title,
            CompanyKnowledgeSource.version == normalized_version,
            CompanyKnowledgeSource.status != "archived",
        )
    )
    if existing.scalar_one_or_none():
        raise SourceImportError("相同制度名称和版本号已存在")

    markdown, warnings = to_markdown(imported, normalized_title)

    source = CompanyKnowledgeSource(
        title=normalized_title,
        version=normalized_version,
        knowledge_type=knowledge_type,
        category=(category or "").strip(),
        source_format=imported.source_format,
        file_name=imported.file_name,
        raw_content=imported.content,
        content_hash=imported.content_hash,
        markdown_content=markdown,
        markdown_hash=content_hash(markdown),
        markdown_version=1,
        conversion_warnings=warnings,
        effective_at=_as_utc(effective_at),
        expires_at=_as_utc(expires_at) if expires_at else None,
        status="markdown_ready",
        metadata_=metadata or {},
        created_by=admin_id,
    )
    job = CompanyKnowledgeJob(
        job_type="convert",
        status="succeeded",
        requested_by=admin_id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add_all([source, job])
    await db.flush()
    job.source_id = source.id
    await db.commit()
    await db.refresh(source)
    return source


async def reindex_company_source(db: AsyncSession, source_id: str, admin_id) -> CompanyKnowledgeSource:
    source = await _get_source(db, source_id)
    chunk_set = await create_chunk_set(
        db,
        source_id=source_id,
        mode="auto",
        rule={"max_chars": 650, "overlap_chars": 100},
        chunks=None,
        admin_id=admin_id,
    )
    await confirm_chunk_set(db, source_id=source_id, chunk_set_id=str(chunk_set.id), admin_id=admin_id)
    await index_chunk_set(db, source_id=source_id, chunk_set_id=str(chunk_set.id), admin_id=admin_id)
    return await _get_source(db, source_id)


async def publish_company_source(db: AsyncSession, source_id: str, admin_id) -> CompanyKnowledgeSource:
    source = await _get_source(db, source_id)
    if source.status == "archived":
        raise CompanyKnowledgeServiceError("已下架资料不能重新发布，请重新上传")
    validated = await db.execute(
        select(CompanyKnowledgeChunkSet)
        .where(
            CompanyKnowledgeChunkSet.source_id == source.id,
            CompanyKnowledgeChunkSet.status == "validated",
        )
        .order_by(CompanyKnowledgeChunkSet.validated_at.desc())
        .limit(1)
    )
    chunk_set = validated.scalar_one_or_none()
    if not chunk_set:
        raise CompanyKnowledgeServiceError("请先完成向量化和检索验证")

    current_sources = await db.execute(
        select(CompanyKnowledgeSource)
        .where(
            CompanyKnowledgeSource.title == source.title,
            CompanyKnowledgeSource.status == "published",
            CompanyKnowledgeSource.id != source.id,
        )
        .order_by(CompanyKnowledgeSource.published_at.desc())
    )
    previous = current_sources.scalars().all()
    if previous:
        source.replaced_source_id = previous[0].id
        for old_source in previous:
            old_source.status = "archived"

    if source.active_chunk_set_id and source.active_chunk_set_id != chunk_set.id:
        previous_set = await db.get(CompanyKnowledgeChunkSet, source.active_chunk_set_id)
        if previous_set:
            previous_set.status = "superseded"
    source.active_chunk_set_id = chunk_set.id
    chunk_set.status = "published"
    source.status = "published"
    source.published_by = admin_id
    source.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(source)
    return source


async def archive_company_source(db: AsyncSession, source_id: str) -> CompanyKnowledgeSource:
    source = await _get_source(db, source_id)
    if source.status == "indexing":
        raise CompanyKnowledgeServiceError("资料正在索引，暂时不能下架")
    source.status = "archived"
    await db.commit()
    await db.refresh(source)
    return source


async def update_company_source_metadata(
    db: AsyncSession,
    *,
    source_id: str,
    title: str,
    version: str,
    effective_at: datetime,
    expires_at: datetime | None,
    category: str,
) -> CompanyKnowledgeSource:
    """仅编辑资料元数据，已发布或正在索引的资料需以新版本替换。"""
    source = await _get_source(db, source_id)
    if source.status in {"published", "indexing"}:
        raise CompanyKnowledgeServiceError("已发布或正在索引的资料不能编辑，请上传新版本")

    normalized_title = title.strip()
    normalized_version = version.strip()
    if not normalized_title or not normalized_version:
        raise CompanyKnowledgeServiceError("资料名称和版本号不能为空")
    if expires_at and _as_utc(expires_at) <= _as_utc(effective_at):
        raise CompanyKnowledgeServiceError("失效时间必须晚于生效时间")

    if source.status != "archived":
        existing = await db.execute(
            select(CompanyKnowledgeSource).where(
                CompanyKnowledgeSource.title == normalized_title,
                CompanyKnowledgeSource.version == normalized_version,
                CompanyKnowledgeSource.id != source.id,
                CompanyKnowledgeSource.status != "archived",
            )
        )
        if existing.scalar_one_or_none():
            raise CompanyKnowledgeServiceError("相同资料名称和版本号已存在")

    source.title = normalized_title
    source.version = normalized_version
    source.category = (category or "").strip()
    source.effective_at = _as_utc(effective_at)
    source.expires_at = _as_utc(expires_at) if expires_at else None
    await db.commit()
    await db.refresh(source)
    return source


async def delete_archived_company_source(db: AsyncSession, source_id: str) -> None:
    """已下架资料可彻底移除；会话中的历史引用快照不受影响。"""
    source = await _get_source(db, source_id)
    if source.status != "archived":
        raise CompanyKnowledgeServiceError("只能删除已下架资料")
    await db.delete(source)
    await db.commit()


async def list_company_sources(
    db: AsyncSession,
    *,
    knowledge_type: str = "policy",
    status: str = "all",
    page: int = 1,
    size: int = 20,
) -> tuple[list[CompanyKnowledgeSource], int]:
    stmt = select(CompanyKnowledgeSource).where(CompanyKnowledgeSource.knowledge_type == knowledge_type)
    count_stmt = select(func.count(CompanyKnowledgeSource.id)).where(CompanyKnowledgeSource.knowledge_type == knowledge_type)
    if status != "all":
        stmt = stmt.where(CompanyKnowledgeSource.status == status)
        count_stmt = count_stmt.where(CompanyKnowledgeSource.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = await db.execute(
        stmt.order_by(CompanyKnowledgeSource.updated_at.desc()).offset((page - 1) * size).limit(size)
    )
    sources = rows.scalars().all()
    if sources:
        for source in sources:
            if not source.active_chunk_set_id:
                source.chunk_count = 0
                continue
            source.chunk_count = await db.scalar(
                select(func.count(CompanyKnowledgeChunk.id)).where(
                    CompanyKnowledgeChunk.chunk_set_id == source.active_chunk_set_id
                )
            ) or 0
    return sources, total


async def list_company_jobs(db: AsyncSession, *, page: int = 1, size: int = 30) -> tuple[list[CompanyKnowledgeJob], int]:
    total = (await db.execute(select(func.count(CompanyKnowledgeJob.id)))).scalar() or 0
    rows = await db.execute(
        select(CompanyKnowledgeJob)
        .order_by(CompanyKnowledgeJob.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return rows.scalars().all(), total


async def delete_company_job(db: AsyncSession, job_id: str) -> None:
    """清理已结束的处理记录，不允许删除仍在执行中的任务。"""
    job = await db.get(CompanyKnowledgeJob, job_id)
    if not job:
        raise CompanyKnowledgeServiceError("处理任务不存在")
    if job.status in {"queued", "running"}:
        raise CompanyKnowledgeServiceError("进行中的处理任务不能删除")
    await db.delete(job)
    await db.commit()


async def get_company_source_detail(
    db: AsyncSession, source_id: str, chunk_set_id: str | None = None
) -> tuple[CompanyKnowledgeSource, list[CompanyKnowledgeChunkSet], list[CompanyKnowledgeChunk]]:
    source = await _get_source(db, source_id)
    sets_result = await db.execute(
        select(CompanyKnowledgeChunkSet)
        .where(CompanyKnowledgeChunkSet.source_id == source.id)
        .order_by(CompanyKnowledgeChunkSet.created_at.desc())
    )
    chunk_sets = sets_result.scalars().all()
    selected_set_id = chunk_set_id or source.active_chunk_set_id or (chunk_sets[0].id if chunk_sets else None)
    if selected_set_id and not any(str(item.id) == str(selected_set_id) for item in chunk_sets):
        raise CompanyKnowledgeServiceError("分片版本不存在")
    if not selected_set_id:
        return source, chunk_sets, []
    chunks_result = await db.execute(
        select(CompanyKnowledgeChunk)
        .where(CompanyKnowledgeChunk.chunk_set_id == selected_set_id)
        .order_by(CompanyKnowledgeChunk.chunk_index.asc())
    )
    return source, chunk_sets, chunks_result.scalars().all()


async def ensure_company_knowledge_session(
    db: AsyncSession,
    user_id: str,
    session_id: str | None,
) -> Session:
    if session_id:
        result = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user_id))
        session = result.scalar_one_or_none()
        if not session:
            raise CompanyKnowledgeServiceError("会话不存在")
        session.updated_at = datetime.now(timezone.utc)
        return session

    session = Session(user_id=user_id, title="公司制度问答")
    db.add(session)
    await db.flush()
    return session


async def save_company_knowledge_user_message(
    db: AsyncSession,
    *,
    session: Session,
    message: str,
    knowledge_type: str,
    input_mode: str,
) -> Message:
    item = Message(
        session_id=session.id,
        role="user",
        content=message,
        msg_type=COMPANY_KNOWLEDGE_MESSAGE_TYPE,
        metadata_=json.dumps(
            {
                "ui_channel": "rag_floating_chat",
                "company_knowledge": {"knowledge_type": knowledge_type, "input_mode": input_mode},
            },
            ensure_ascii=False,
        ),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def save_company_knowledge_answer(
    db: AsyncSession,
    *,
    session: Session,
    question: str,
    answer: str,
    knowledge_type: str,
    citations: list[dict],
) -> Message:
    item = Message(
        session_id=session.id,
        role="agent",
        content=answer,
        msg_type=COMPANY_KNOWLEDGE_MESSAGE_TYPE,
        metadata_=json.dumps(
            {
                "ui_channel": "rag_floating_chat",
                "company_knowledge": {
                    "knowledge_type": knowledge_type,
                    "citations": citations,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            ensure_ascii=False,
        ),
    )
    db.add(item)
    if not session.title_auto_set and session.title in {"", "新对话", "公司制度问答"}:
        session.title = question[:30] or "公司制度问答"
        session.title_auto_set = True
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item


async def create_chunk_set(
    db: AsyncSession,
    *,
    source_id: str,
    mode: str,
    rule: dict | None,
    chunks: list[dict] | None,
    admin_id,
) -> CompanyKnowledgeChunkSet:
    source = await _get_source(db, source_id)
    if source.status == "archived":
        raise CompanyKnowledgeServiceError("已下架资料不能新建切分草稿")
    if mode not in {"auto", "manual", "auto_then_manual"}:
        raise CompanyKnowledgeServiceError("不支持的切分方式")

    rule_snapshot = _normalize_chunk_rule(rule)
    if mode in {"auto", "auto_then_manual"}:
        generated = chunk_text(
            source.markdown_content or source.raw_content,
            source_format="md",
            max_chars=rule_snapshot["max_chars"],
            overlap_chars=rule_snapshot["overlap_chars"],
        )
        chunk_items = [
            {"section_path": item.section_path, "content": item.content, "token_count": item.token_count}
            for item in generated
        ]
    else:
        chunk_items = chunks or [{"section_path": "", "content": source.markdown_content or source.raw_content}]

    normalized_chunks = _normalize_chunk_items(chunk_items)
    if not normalized_chunks:
        raise CompanyKnowledgeServiceError("请至少保留一个有效分片")

    chunk_set = CompanyKnowledgeChunkSet(
        source_id=source.id,
        markdown_version=source.markdown_version,
        mode=mode,
        status="draft",
        rule_snapshot=rule_snapshot if mode != "manual" else {},
        created_by=admin_id,
        total_chunks=len(normalized_chunks),
    )
    db.add(chunk_set)
    await db.flush()
    await _replace_chunk_items(db, source, chunk_set, normalized_chunks)
    db.add(
        CompanyKnowledgeJob(
            source_id=source.id,
            chunk_set_id=chunk_set.id,
            job_type="auto_chunk" if mode != "manual" else "manual_chunk",
            status="succeeded",
            requested_by=admin_id,
            total_chunks=len(normalized_chunks),
            succeeded_chunks=len(normalized_chunks),
            request_snapshot={"mode": mode, "rule": chunk_set.rule_snapshot},
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
    )
    if source.status != "published":
        source.status = "chunking"
    await db.commit()
    await db.refresh(chunk_set)
    return chunk_set


async def update_chunk_set(
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    chunks: list[dict],
) -> CompanyKnowledgeChunkSet:
    source = await _get_source(db, source_id)
    chunk_set = await _get_chunk_set(db, source.id, chunk_set_id)
    if chunk_set.status != "draft":
        raise CompanyKnowledgeServiceError("只有草稿分片可以编辑")
    normalized_chunks = _normalize_chunk_items(chunks)
    if not normalized_chunks:
        raise CompanyKnowledgeServiceError("请至少保留一个有效分片")
    await _replace_chunk_items(db, source, chunk_set, normalized_chunks)
    chunk_set.total_chunks = len(normalized_chunks)
    await db.commit()
    await db.refresh(chunk_set)
    return chunk_set


async def confirm_chunk_set(
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    admin_id,
) -> CompanyKnowledgeChunkSet:
    source = await _get_source(db, source_id)
    chunk_set = await _get_chunk_set(db, source.id, chunk_set_id)
    if chunk_set.status != "draft":
        raise CompanyKnowledgeServiceError("该分片版本不能确认")
    count = await db.scalar(
        select(func.count(CompanyKnowledgeChunk.id)).where(CompanyKnowledgeChunk.chunk_set_id == chunk_set.id)
    )
    if not count:
        raise CompanyKnowledgeServiceError("请至少保留一个有效分片")
    chunk_set.status = "confirmed"
    chunk_set.confirmed_by = admin_id
    chunk_set.confirmed_at = datetime.now(timezone.utc)
    chunk_set.total_chunks = count
    if source.status != "published":
        source.status = "chunk_ready"
    await db.commit()
    await db.refresh(chunk_set)
    return chunk_set


async def index_chunk_set(
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    admin_id,
) -> CompanyKnowledgeChunkSet:
    source = await _get_source(db, source_id)
    chunk_set = await _get_chunk_set(db, source.id, chunk_set_id)
    if chunk_set.status != "confirmed":
        raise CompanyKnowledgeServiceError("请先确认分片后再向量化")
    rows = await db.execute(
        select(CompanyKnowledgeChunk)
        .where(CompanyKnowledgeChunk.chunk_set_id == chunk_set.id)
        .order_by(CompanyKnowledgeChunk.chunk_index.asc())
    )
    chunks = rows.scalars().all()
    if not chunks:
        raise CompanyKnowledgeServiceError("该分片版本没有有效内容")

    previous_source_status = source.status
    job = CompanyKnowledgeJob(
        source_id=source.id,
        chunk_set_id=chunk_set.id,
        job_type="index",
        status="running",
        requested_by=admin_id,
        total_chunks=len(chunks),
        started_at=datetime.now(timezone.utc),
    )
    chunk_set.status = "indexing"
    if source.status != "published":
        source.status = "indexing"
    db.add(job)
    await db.commit()

    try:
        vectors = await _embed_chunks(chunks)
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
            chunk.status = "indexed"
        chunk_set.status = "indexed"
        chunk_set.indexed_chunks = len(chunks)
        chunk_set.indexed_at = datetime.now(timezone.utc)
        job.status = "succeeded"
        job.succeeded_chunks = len(chunks)
        job.finished_at = datetime.now(timezone.utc)
        if previous_source_status != "published":
            source.status = "indexed"
        await db.commit()
        await db.refresh(chunk_set)
        return chunk_set
    except Exception as exc:
        await db.rollback()
        source = await _get_source(db, source_id)
        chunk_set = await _get_chunk_set(db, source.id, chunk_set_id)
        failed_job = await db.get(CompanyKnowledgeJob, job.id)
        source.status = previous_source_status
        chunk_set.status = "confirmed"
        if failed_job:
            failed_job.status = "failed"
            failed_job.error_message = str(exc)[:2000]
            failed_job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise CompanyKnowledgeServiceError("向量化失败") from exc


async def validate_chunk_set(
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    admin_id,
) -> CompanyKnowledgeChunkSet:
    """管理员确认已通过检索验证，允许该分片版本进入发布流程。"""
    source = await _get_source(db, source_id)
    chunk_set = await _get_chunk_set(db, source.id, chunk_set_id)
    if chunk_set.status == "validated":
        return chunk_set
    if chunk_set.status != "indexed":
        raise CompanyKnowledgeServiceError("请先完成向量化，再执行检索验证")

    chunk_set.status = "validated"
    chunk_set.validated_by = admin_id
    chunk_set.validated_at = datetime.now(timezone.utc)
    if source.status != "published":
        source.status = "validated"
    await db.commit()
    await db.refresh(chunk_set)
    return chunk_set


async def _replace_chunk_items(
    db: AsyncSession,
    source: CompanyKnowledgeSource,
    chunk_set: CompanyKnowledgeChunkSet,
    chunks: list[dict],
) -> None:
    await db.execute(delete(CompanyKnowledgeChunk).where(CompanyKnowledgeChunk.chunk_set_id == chunk_set.id))
    db.add_all(
        [
            CompanyKnowledgeChunk(
                source_id=source.id,
                chunk_set_id=chunk_set.id,
                chunk_index=index,
                section_path=item["section_path"],
                content=item["content"],
                content_hash=_content_hash(item["content"]),
                token_count=item["token_count"],
                status="draft",
                metadata_={"markdown_version": source.markdown_version},
            )
            for index, item in enumerate(chunks)
        ]
    )
    await db.flush()


async def _embed_chunks(chunks: list[CompanyKnowledgeChunk]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[start:start + EMBEDDING_BATCH_SIZE]
        batch_vectors = await get_embeddings_batch([chunk.content for chunk in batch])
        if not batch_vectors or len(batch_vectors) != len(batch):
            raise CompanyKnowledgeServiceError("向量生成失败")
        vectors.extend(batch_vectors)
    return vectors


def _normalize_chunk_rule(rule: dict | None) -> dict:
    incoming = rule or {}
    max_chars = int(incoming.get("max_chars", 650))
    overlap_chars = int(incoming.get("overlap_chars", 100))
    if max_chars < 120 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise CompanyKnowledgeServiceError("切分长度或重叠长度不合法")
    return {"max_chars": max_chars, "overlap_chars": overlap_chars}


def _normalize_chunk_items(chunks: list[dict]) -> list[dict]:
    normalized = []
    for item in chunks:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        normalized.append(
            {
                "section_path": str(item.get("section_path") or "").strip(),
                "content": content,
                "token_count": max(1, (len(content) + 1) // 2),
            }
        )
    return normalized


async def _mark_index_failure(db: AsyncSession, source_id, job_id, exc: Exception) -> None:
    await db.rollback()
    source = await db.get(CompanyKnowledgeSource, source_id)
    job = await db.get(CompanyKnowledgeJob, job_id)
    if source:
        source.status = "failed"
    if job:
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        job.finished_at = datetime.now(timezone.utc)
    await db.commit()


async def _get_source(db: AsyncSession, source_id: str) -> CompanyKnowledgeSource:
    source = await db.get(CompanyKnowledgeSource, source_id)
    if not source:
        raise CompanyKnowledgeServiceError("资料不存在")
    return source


async def _get_chunk_set(
    db: AsyncSession, source_id, chunk_set_id: str
) -> CompanyKnowledgeChunkSet:
    chunk_set = await db.get(CompanyKnowledgeChunkSet, chunk_set_id)
    if not chunk_set or chunk_set.source_id != source_id:
        raise CompanyKnowledgeServiceError("分片版本不存在")
    return chunk_set


def _ensure_import_enabled(knowledge_type: str) -> None:
    item = get_knowledge_type(knowledge_type)
    if not item:
        raise SourceImportError("未知资料类型")
    if not is_import_enabled(knowledge_type):
        raise SourceImportError(f"{item.label}暂未启用导入")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _content_hash(content: str) -> str:
    from hashlib import sha256

    return sha256(content.encode("utf-8")).hexdigest()
