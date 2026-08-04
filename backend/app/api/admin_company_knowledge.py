from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import get_current_admin
from app.api.response import fail, ok
from app.db.session import get_db
from app.models.billing import Admin
from app.plugins.company_knowledge.importer import SourceImportError
from app.plugins.company_knowledge.retriever import (
    MIN_SIMILARITY,
    RetrievalError,
    preview_company_knowledge_chunk_set,
)
from app.plugins.company_knowledge.registry import get_knowledge_type, list_knowledge_types
from app.plugins.company_knowledge.service import (
    CompanyKnowledgeServiceError,
    archive_company_source,
    chunk_set_to_dict,
    chunk_to_dict,
    confirm_chunk_set,
    create_chunk_set,
    delete_archived_company_source,
    delete_company_job,
    get_company_source_detail,
    import_company_source,
    index_chunk_set,
    job_to_dict,
    list_company_jobs,
    list_company_sources,
    publish_company_source,
    reindex_company_source,
    source_to_dict,
    update_chunk_set,
    update_company_source_metadata,
    validate_chunk_set,
)


router = APIRouter(prefix="/api/admin/company-knowledge", tags=["admin"])


class ChunkInput(BaseModel):
    section_path: str = ""
    content: str


class CreateChunkSetRequest(BaseModel):
    mode: str = "auto"
    rule: dict = Field(default_factory=dict)
    chunks: list[ChunkInput] | None = None


class UpdateChunkSetRequest(BaseModel):
    chunks: list[ChunkInput]


class UpdateSourceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    effective_at: datetime
    expires_at: datetime | None = None
    category: str = Field(default="", max_length=64)


class RetrievalPreviewRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=10)
    expected_chunk_ids: list[str] = Field(default_factory=list, max_length=10)


async def _run_retrieval_preview(
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    req: RetrievalPreviewRequest,
) -> dict:
    _, chunk_sets, chunks = await get_company_source_detail(db, source_id, chunk_set_id)
    chunk_set = next((item for item in chunk_sets if str(item.id) == chunk_set_id), None)
    if not chunk_set or chunk_set.status not in {"indexed", "validated"}:
        raise CompanyKnowledgeServiceError("请先完成向量化，再进行检索验证")
    available_ids = {str(item.id) for item in chunks}
    if any(item_id not in available_ids for item_id in req.expected_chunk_ids):
        raise CompanyKnowledgeServiceError("预期分片不属于当前分片版本")
    matches = await preview_company_knowledge_chunk_set(
        req.question.strip(),
        db,
        source_id=source_id,
        chunk_set_id=chunk_set_id,
        top_k=req.top_k,
    )
    items = [item.to_preview() for item in matches]
    returned_ids = {item["chunk_id"] for item in items}
    expected_ids = set(req.expected_chunk_ids)
    return {
        "items": items,
        "minimum_similarity": MIN_SIMILARITY,
        "above_threshold_count": sum(item["meets_minimum_similarity"] for item in items),
        "expected_chunk_ids": req.expected_chunk_ids,
        "expected_hit": bool(returned_ids & expected_ids) if expected_ids else None,
    }


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
    if status not in {"all", "markdown_ready", "chunking", "chunk_ready", "indexing", "indexed", "validated", "published", "failed", "archived"}:
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
    chunk_set_id: str | None = Query(default=None),
):
    try:
        source, chunk_sets, chunks = await get_company_source_detail(db, source_id, chunk_set_id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok(
        {
            "source": source_to_dict(source),
            "markdown": source.markdown_content,
            "chunk_sets": [chunk_set_to_dict(item) for item in chunk_sets],
            "chunks": [chunk_to_dict(chunk) for chunk in chunks],
            "selected_chunk_set_id": str(source.active_chunk_set_id) if source.active_chunk_set_id else (str(chunk_sets[0].id) if chunk_sets else None),
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
    return ok({"source": source_to_dict(source)}, "资料已转换为 Markdown，请进入切分细则确认分片")


@router.put("/sources/{source_id}")
async def update_source(
    source_id: str,
    req: UpdateSourceRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await update_company_source_metadata(
            db,
            source_id=source_id,
            title=req.title,
            version=req.version,
            effective_at=req.effective_at,
            expires_at=req.expires_at,
            category=req.category,
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"source": source_to_dict(source)}, "资料信息已更新")


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_archived_company_source(db, source_id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({}, "已删除下架资料")


@router.post("/sources/{source_id}/chunk-sets")
async def create_source_chunk_set(
    source_id: str,
    req: CreateChunkSetRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        chunk_set = await create_chunk_set(
            db,
            source_id=source_id,
            mode=req.mode,
            rule=req.rule,
            chunks=[item.model_dump() for item in req.chunks] if req.chunks is not None else None,
            admin_id=admin.id,
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"chunk_set": chunk_set_to_dict(chunk_set)}, "已生成分片草稿")


@router.put("/sources/{source_id}/chunk-sets/{chunk_set_id}")
async def update_source_chunk_set(
    source_id: str,
    chunk_set_id: str,
    req: UpdateChunkSetRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        chunk_set = await update_chunk_set(
            db,
            source_id=source_id,
            chunk_set_id=chunk_set_id,
            chunks=[item.model_dump() for item in req.chunks],
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"chunk_set": chunk_set_to_dict(chunk_set)}, "分片草稿已保存")


@router.post("/sources/{source_id}/chunk-sets/{chunk_set_id}/confirm")
async def confirm_source_chunk_set(
    source_id: str,
    chunk_set_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        chunk_set = await confirm_chunk_set(
            db, source_id=source_id, chunk_set_id=chunk_set_id, admin_id=admin.id
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"chunk_set": chunk_set_to_dict(chunk_set)}, "分片已确认，可以向量化")


@router.post("/sources/{source_id}/chunk-sets/{chunk_set_id}/index")
async def index_source_chunk_set(
    source_id: str,
    chunk_set_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        chunk_set = await index_chunk_set(
            db, source_id=source_id, chunk_set_id=chunk_set_id, admin_id=admin.id
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({"chunk_set": chunk_set_to_dict(chunk_set)}, "分片已完成向量化，可以发布")


@router.post("/sources/{source_id}/chunk-sets/{chunk_set_id}/retrieval-preview")
async def preview_source_chunk_set_retrieval(
    source_id: str,
    chunk_set_id: str,
    req: RetrievalPreviewRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """发布前只检索当前分片集，便于审核切分与向量化质量。"""
    try:
        result = await _run_retrieval_preview(
            db, source_id=source_id, chunk_set_id=chunk_set_id, req=req
        )
    except (CompanyKnowledgeServiceError, RetrievalError) as exc:
        return fail(str(exc))
    return ok(result)


@router.post("/sources/{source_id}/chunk-sets/{chunk_set_id}/validate")
async def validate_source_chunk_set(
    source_id: str,
    chunk_set_id: str,
    req: RetrievalPreviewRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        preview = await _run_retrieval_preview(
            db, source_id=source_id, chunk_set_id=chunk_set_id, req=req
        )
        if not preview["above_threshold_count"]:
            raise CompanyKnowledgeServiceError("检索结果均未达到最低相似度，不能确认发布")
        if req.expected_chunk_ids and not preview["expected_hit"]:
            raise CompanyKnowledgeServiceError("预期分片未命中，不能确认发布")
        chunk_set = await validate_chunk_set(
            db, source_id=source_id, chunk_set_id=chunk_set_id, admin_id=admin.id
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok(
        {"chunk_set": chunk_set_to_dict(chunk_set), "preview": preview},
        "检索验证已确认，可以发布",
    )


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


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_company_job(db, job_id)
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc))
    return ok({}, "处理任务记录已删除")
