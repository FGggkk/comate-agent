from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder


async def create(user_id: str, content: str, remind_at: datetime, db: AsyncSession) -> dict:
    reminder = Reminder(user_id=user_id, content=content, remind_at=remind_at)
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return {"id": str(reminder.id), "content": reminder.content, "remind_at": reminder.remind_at.isoformat()}


async def list_reminders(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.remind_at.asc())
    )
    items = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "content": r.content,
            "remind_at": r.remind_at.isoformat(),
            "triggered": r.triggered,
        }
        for r in items
    ]


async def delete_reminder(user_id: str, reminder_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        delete(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        return {"success": False, "message": "提醒不存在或无权操作"}
    return {"success": True}


async def get_due_reminders(user_id: str, db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.triggered == False,
            Reminder.remind_at <= now,
        )
    )
    items = result.scalars().all()
    due = []
    for r in items:
        r.triggered = True
        due.append({"id": str(r.id), "content": r.content, "remind_at": r.remind_at.isoformat()})

    if due:
        await db.commit()

    return due
