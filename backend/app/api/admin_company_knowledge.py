from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import get_current_admin
from app.api.response import fail, ok
from app.db.session import get_db
from app.models.billing import Admin
from app.models.company_knowledge import CompanyKnowledgeChunk
from app.plugins.company_knowledge.importer import SourceImportError
from app.plugins.company_knowledge.registry import get_knowledge_type, list_knowledge_types
from app.plugins.company_knowledge.service import (
    CompanyKnowledgeServiceError,
    archive_company_source,
    get_company_source_detail,
    import_company_source,
    job_to_dict,
    list_company_jobs,
    list_company_sources,
    publish_company_source,
    reindex_company_source,
    source_to_dict,
)


router = APIRouter(prefix="/api/admin/company-knowledge", tags=["admin"])


@router.get("/types")
async def list_admin_types(admin: Admin = Depends(get_current_admin)):
    """管理端使用同一资料类型注册表，不在页面中分散维护枚举。"""
    return ok({"items": list_knowledge_types()})


@router.get("/sources")
async def list_sources(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    knowledge_type: str = Query(default="policy"),
    status: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    if not get_knowledge_type(knowledge_type):
        return fail("未知资料类型")
    if status not in {"all", "draft", "indexing", "published", "failed", "archived"}:
        return fail("未知资料状态")
    items, total = await list_company_sources(
        db,
        knowledge_type=knowledge_type,
        status=status,
        page=page,
        size=size,
    )
    return ok({"items": [source_to_dict(item) for item in items], "total": total, "page": page, "size": size})


@router.get("/sources/{source_id}")
async def get_source(
    source_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        source, chunks = await get_company_source_detail(db, source_id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok(
        {
            "source": source_to_dict(source),
            "chunks": [_chunk_to_dict(chunk) for chunk in chunks],
            "preview_limited": len(chunks) == 12,
        }
    )


@router.post("/sources")
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    version: str = Form(...),
    effective_at: datetime = Form(...),
    expires_at: datetime | None = Form(default=None),
    category: str = Form(default=""),
    knowledge_type: str = Form(default="policy"),
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await import_company_source(
            db,
            file_name=file.filename or "",
            file_content=await file.read(),
            title=title,
            version=version,
            knowledge_type=knowledge_type,
            effective_at=effective_at,
            expires_at=expires_at,
            category=category,
            metadata=None,
            admin_id=admin.id,
        )
    except (SourceImportError, CompanyKnowledgeServiceError) as exc:
        return fail(str(exc))
    return ok({"source": source_to_dict(source)}, "资料已完成索引，等待发布")


@router.post("/sources/{source_id}/publish")
async def publish_source(
    source_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await publish_company_source(db, source_id, admin.id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"source": source_to_dict(source)}, "制度已发布")


@router.post("/sources/{source_id}/archive")
async def archive_source(
    source_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await archive_company_source(db, source_id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"source": source_to_dict(source)}, "制度已下架")


@router.post("/sources/{source_id}/reindex")
async def reindex_source(
    source_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await reindex_company_source(db, source_id, admin.id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"source": source_to_dict(source)}, "资料已重新索引")


@router.get("/jobs")
async def list_jobs(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=30, ge=1, le=100),
):
    items, total = await list_company_jobs(db, page=page, size=size)
    return ok({"items": [job_to_dict(item) for item in items], "total": total, "page": page, "size": size})


def _chunk_to_dict(chunk: CompanyKnowledgeChunk) -> dict:
    return {
        "id": str(chunk.id),
        "chunk_index": chunk.chunk_index,
        "section_path": chunk.section_path,
        "content": chunk.content,
        "token_count": chunk.token_count,
    }
