"""公司资料导入、发布、版本替换与会话写入服务。"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge import CompanyKnowledgeChunk, CompanyKnowledgeJob, CompanyKnowledgeSource
from app.models.conversation import Message, Session
from app.plugins.company_knowledge.chunker import chunk_text
from app.plugins.company_knowledge.importer import ImportedText, SourceImportError, read_text_source
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
        "created_at": _format_datetime(source.created_at),
        "updated_at": _format_datetime(source.updated_at),
        "published_at": _format_datetime(source.published_at),
        "chunk_count": getattr(source, "chunk_count", None),
        "error_message": getattr(source, "error_message", None),
    }


def job_to_dict(job: CompanyKnowledgeJob) -> dict:
    return {
        "id": str(job.id),
        "source_id": str(job.source_id) if job.source_id else None,
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
        )
    )
    if existing.scalar_one_or_none():
        raise SourceImportError("相同制度名称和版本号已存在")

    source = CompanyKnowledgeSource(
        title=normalized_title,
        version=normalized_version,
        knowledge_type=knowledge_type,
        category=(category or "").strip(),
        source_format=imported.source_format,
        file_name=imported.file_name,
        raw_content=imported.content,
        content_hash=imported.content_hash,
        effective_at=_as_utc(effective_at),
        expires_at=_as_utc(expires_at) if expires_at else None,
        status="indexing",
        metadata_=metadata or {},
        created_by=admin_id,
    )
    job = CompanyKnowledgeJob(
        job_type="import",
        status="running",
        requested_by=admin_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add_all([source, job])
    await db.flush()
    job.source_id = source.id
    await db.commit()
    await db.refresh(source)
    await db.refresh(job)

    try:
        await _index_source(db, source, job)
        source.status = "draft"
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(source)
        return source
    except Exception as exc:
        await _mark_index_failure(db, source.id, job.id, exc)
        raise CompanyKnowledgeServiceError(str(exc)) from exc


async def reindex_company_source(db: AsyncSession, source_id: str, admin_id) -> CompanyKnowledgeSource:
    source = await _get_source(db, source_id)
    _ensure_import_enabled(source.knowledge_type)
    previous_status = source.status
    job = CompanyKnowledgeJob(
        source_id=source.id,
        job_type="reindex",
        status="running",
        requested_by=admin_id,
        started_at=datetime.now(timezone.utc),
    )
    source.status = "indexing"
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        await _index_source(db, source, job, replace_existing=True)
        source.status = "draft" if previous_status != "published" else "published"
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(source)
        return source
    except Exception as exc:
        await db.rollback()
        source = await _get_source(db, source_id)
        failed_job = await db.get(CompanyKnowledgeJob, job.id)
        source.status = previous_status
        if failed_job:
            failed_job.status = "failed"
            failed_job.error_message = str(exc)[:2000]
            failed_job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise CompanyKnowledgeServiceError(str(exc)) from exc


async def publish_company_source(db: AsyncSession, source_id: str, admin_id) -> CompanyKnowledgeSource:
    source = await _get_source(db, source_id)
    if source.status != "draft":
        raise CompanyKnowledgeServiceError("只有索引成功的草稿资料可以发布")

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
        chunk_counts = await db.execute(
            select(CompanyKnowledgeChunk.source_id, func.count(CompanyKnowledgeChunk.id))
            .where(CompanyKnowledgeChunk.source_id.in_([source.id for source in sources]))
            .group_by(CompanyKnowledgeChunk.source_id)
        )
        count_by_source = {source_id: count for source_id, count in chunk_counts.all()}
        for source in sources:
            source.chunk_count = count_by_source.get(source.id, 0)
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


async def get_company_source_detail(db: AsyncSession, source_id: str) -> tuple[CompanyKnowledgeSource, list[CompanyKnowledgeChunk]]:
    source = await _get_source(db, source_id)
    result = await db.execute(
        select(CompanyKnowledgeChunk)
        .where(CompanyKnowledgeChunk.source_id == source.id)
        .order_by(CompanyKnowledgeChunk.chunk_index.asc())
        .limit(12)
    )
    return source, result.scalars().all()


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
            {"company_knowledge": {"knowledge_type": knowledge_type, "input_mode": input_mode}},
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


async def _index_source(
    db: AsyncSession,
    source: CompanyKnowledgeSource,
    job: CompanyKnowledgeJob,
    *,
    replace_existing: bool = False,
) -> None:
    chunks = chunk_text(source.raw_content, source_format=source.source_format)
    if not chunks:
        raise CompanyKnowledgeServiceError("资料未生成有效分片")

    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[start:start + EMBEDDING_BATCH_SIZE]
        batch_vectors = await get_embeddings_batch([chunk.content for chunk in batch])
        if not batch_vectors or len(batch_vectors) != len(batch):
            raise CompanyKnowledgeServiceError("向量生成失败")
        vectors.extend(batch_vectors)

    if replace_existing:
        await db.execute(delete(CompanyKnowledgeChunk).where(CompanyKnowledgeChunk.source_id == source.id))
    db.add_all(
        [
            CompanyKnowledgeChunk(
                source_id=source.id,
                chunk_index=chunk.chunk_index,
                section_path=chunk.section_path,
                content=chunk.content,
                content_hash=_content_hash(chunk.content),
                token_count=chunk.token_count,
                embedding=vector,
                metadata_={"source_format": source.source_format},
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
    )
    job.total_chunks = len(chunks)
    job.succeeded_chunks = len(chunks)
    job.failed_chunks = 0
    await db.flush()


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
