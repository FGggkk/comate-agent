from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import get_db
from app.services import memory_document_service, memory_service

router = APIRouter(prefix="/api/memories", tags=["memories"])


class UpdateMemoryRequest(BaseModel):
    summary: str | None = None
    memory_type: str | None = None
    content: dict | None = None
    user_confirmed: bool | None = None
    scope: str | None = None
    topic_tags: list[str] | None = None
    event_at: datetime | None = None
    expires_at: datetime | None = None
    confidence: float | None = None
    observed_count: int | None = None
    last_observed_at: datetime | None = None
    review_after: datetime | None = None


class CreateMemoryRequest(BaseModel):
    summary: str
    memory_type: str = "general"
    content: dict | None = None
    scope: str | None = None
    topic_tags: list[str] | None = None
    event_at: datetime | None = None
    expires_at: datetime | None = None
    confidence: float | None = None
    observed_count: int | None = None
    last_observed_at: datetime | None = None
    review_after: datetime | None = None


class AddForbiddenRequest(BaseModel):
    topic_summary: str
    original_phrase: str = ""


class MemoryDocumentUpdateRequest(BaseModel):
    content: str
    export_to_file: bool = False


class MemoryDocumentRebuildRequest(BaseModel):
    doc_type: str | None = None
    export_to_file: bool = False


@router.get("")
async def api_get_memories(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok(await memory_service.get_all(user_id, db))


@router.get("/documents")
async def api_get_memory_documents(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok(await memory_document_service.list_document_workspace(user_id, db))


@router.get("/documents/{doc_type}")
async def api_get_memory_document(
    doc_type: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        result = await memory_document_service.ensure_document(user_id, doc_type, db)
        document = result.get("document") or {}
        document["file_status"] = await memory_document_service.get_document_file_status(user_id, doc_type, db)
        return ok(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/documents/rebuild")
async def api_rebuild_memory_documents(
    req: MemoryDocumentRebuildRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        if req.doc_type:
            result = await memory_document_service.rebuild_document_by_type(user_id, req.doc_type, db)
            if req.export_to_file:
                result = await memory_document_service.export_document_to_file(user_id, req.doc_type, db)
            return result
        result = await memory_document_service.rebuild_all_memory_documents(user_id, db)
        if req.export_to_file:
            result["export"] = await memory_document_service.export_all_documents_to_files(user_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/documents/{doc_type}")
async def api_update_memory_document(
    doc_type: str,
    req: MemoryDocumentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        return await memory_document_service.save_document_content(
            user_id,
            doc_type,
            req.content,
            db,
            export_to_file=req.export_to_file,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/documents/{doc_type}/export")
async def api_export_memory_document(
    doc_type: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        return await memory_document_service.export_document_to_file(user_id, doc_type, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/documents/{doc_type}/import")
async def api_import_memory_document(
    doc_type: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        return await memory_document_service.import_document_from_file(user_id, doc_type, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("")
async def api_create_memory(
    req: CreateMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await memory_service.create_co_created(
        user_id=user_id,
        summary=req.summary,
        memory_type=req.memory_type,
        content=req.content,
        scope=req.scope,
        topic_tags=req.topic_tags,
        event_at=req.event_at,
        expires_at=req.expires_at,
        confidence=req.confidence,
        observed_count=req.observed_count,
        last_observed_at=req.last_observed_at,
        review_after=req.review_after,
        db=db,
    )


@router.post("/{item_id}/reminder")
async def api_create_memory_reminder(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await memory_service.create_event_reminder(user_id, item_id, db)


@router.put("/{item_id}")
async def api_update_memory(
    item_id: str,
    req: UpdateMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    data = {}
    if req.summary is not None:
        data["summary"] = req.summary
    if req.memory_type is not None:
        data["memory_type"] = req.memory_type
    if req.content is not None:
        data["content"] = req.content
    if req.user_confirmed is not None:
        data["user_confirmed"] = req.user_confirmed
    if req.scope is not None:
        data["scope"] = req.scope
    if req.topic_tags is not None:
        data["topic_tags"] = req.topic_tags
    if req.event_at is not None:
        data["event_at"] = req.event_at
    if req.expires_at is not None:
        data["expires_at"] = req.expires_at
    if req.confidence is not None:
        data["confidence"] = req.confidence
    if req.observed_count is not None:
        data["observed_count"] = req.observed_count
    if req.last_observed_at is not None:
        data["last_observed_at"] = req.last_observed_at
    if req.review_after is not None:
        data["review_after"] = req.review_after
    return await memory_service.update_item(user_id, item_id, data, db)


@router.delete("/{item_id}")
async def api_delete_memory(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await memory_service.delete_item(user_id, item_id, db)


@router.post("/forbidden")
async def api_add_forbidden(req: AddForbiddenRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await memory_service.add_forbidden(user_id, req.topic_summary, req.original_phrase, db)


@router.delete("/forbidden/{topic_id}")
async def api_remove_forbidden(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await memory_service.remove_forbidden(user_id, topic_id, db)


@router.post("/anchor/{anchor_id}/fulfill")
async def api_fulfill_anchor(
    anchor_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await memory_service.fulfill_anchor(user_id, anchor_id, db)
