from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import get_db
from app.services import reminder_service

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


class CreateRequest(BaseModel):
    content: str
    remind_at: datetime


@router.post("")
async def api_create(req: CreateRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok(await reminder_service.create(user_id, req.content, req.remind_at, db))


@router.get("")
async def api_list(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok({"reminders": await reminder_service.list_reminders(user_id, db)})


@router.delete("/{reminder_id}")
async def api_delete(
    reminder_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await reminder_service.delete_reminder(user_id, reminder_id, db)


@router.get("/due")
async def api_due(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok({"due": await reminder_service.get_due_reminders(user_id, db)})
