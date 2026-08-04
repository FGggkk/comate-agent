import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.api.response import ok, fail
from app.models.conversation import Session, Message

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def parse_message_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


class CreateSessionRequest(BaseModel):
    title: str = "新对话"


class UpdateSessionRequest(BaseModel):
    title: str | None = None


@router.get("")
async def list_sessions(user_id: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).where(Session.user_id == user_id).order_by(Session.updated_at.desc()).limit(50)
    )
    sessions = result.scalars().all()
    return ok({
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    })


@router.post("")
async def create_session(
    req: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = Session(user_id=user_id, title=req.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return ok({
        "id": str(session.id),
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    })


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    req: UpdateSessionRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return fail("会话不存在")
    if req.title is not None:
        session.title = req.title
        session.title_auto_set = True
    await db.commit()
    return {"success": True, "title": session.title}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        return fail("会话不存在")
    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()
    return {"success": True}


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        return fail("会话不存在")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id, Message.msg_type != "company_knowledge")
        .order_by(Message.created_at.asc())
        .limit(100)
    )
    messages = result.scalars().all()
    return ok({
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "type": m.msg_type,
                "metadata": parse_message_metadata(m.metadata_),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    })
