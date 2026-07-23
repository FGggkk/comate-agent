from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services import memory_service

router = APIRouter(prefix="/api/memories", tags=["memories"])


class UpdateMemoryRequest(BaseModel):
    summary: str | None = None
    content: dict | None = None


class AddForbiddenRequest(BaseModel):
    topic_summary: str
    original_phrase: str = ""


@router.get("")
async def api_get_memories(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await memory_service.get_all(user_id, db)


@router.put("/{item_id}")
async def api_update_memory(item_id: str, req: UpdateMemoryRequest, db: AsyncSession = Depends(get_db)):
    data = {}
    if req.summary is not None:
        data["summary"] = req.summary
    if req.content is not None:
        data["content"] = req.content
    return await memory_service.update_item(item_id, data, db)


@router.delete("/{item_id}")
async def api_delete_memory(item_id: str, db: AsyncSession = Depends(get_db)):
    return await memory_service.delete_item(item_id, db)


@router.post("/forbidden")
async def api_add_forbidden(req: AddForbiddenRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await memory_service.add_forbidden(user_id, req.topic_summary, req.original_phrase, db)


@router.delete("/forbidden/{topic_id}")
async def api_remove_forbidden(topic_id: str, db: AsyncSession = Depends(get_db)):
    return await memory_service.remove_forbidden(topic_id, db)


@router.post("/anchor/{anchor_id}/fulfill")
async def api_fulfill_anchor(anchor_id: str, db: AsyncSession = Depends(get_db)):
    return await memory_service.fulfill_anchor(anchor_id, db)
