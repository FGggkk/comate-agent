from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.conversation import Message, Session

router = APIRouter(prefix="/api/messages", tags=["messages"])


class UpdateMessageRequest(BaseModel):
    content: str


@router.put("/{message_id}")
async def update_message(
    message_id: str,
    req: UpdateMessageRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑用户消息"""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        return {"success": False, "message": "消息不存在"}
    if msg.role != "user":
        return {"success": False, "message": "只能编辑用户消息"}

    # 确认消息属于当前用户的会话
    sess_result = await db.execute(
        select(Session).where(Session.id == msg.session_id, Session.user_id == user_id)
    )
    if not sess_result.scalar_one_or_none():
        return {"success": False, "message": "无权操作"}

    # 更新消息内容
    msg.content = req.content
    await db.commit()

    # 删除该消息之后的所有消息
    after = await db.execute(
        select(Message).where(
            Message.session_id == msg.session_id,
            Message.created_at > msg.created_at,
        ).order_by(Message.created_at.desc())
    )
    for m in after.scalars().all():
        await db.delete(m)
    await db.commit()

    return {"success": True, "content": msg.content, "session_id": str(msg.session_id)}


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除用户消息及之后所有消息"""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        return {"success": False, "message": "消息不存在"}

    # 确认归属
    sess_result = await db.execute(
        select(Session).where(Session.id == msg.session_id, Session.user_id == user_id)
    )
    if not sess_result.scalar_one_or_none():
        return {"success": False, "message": "无权操作"}

    session_id = str(msg.session_id)

    # 删除该消息及之后所有消息
    after = await db.execute(
        select(Message).where(
            Message.session_id == msg.session_id,
            Message.created_at >= msg.created_at,
        ).order_by(Message.created_at.desc())
    )
    for m in after.scalars().all():
        await db.delete(m)
    await db.commit()

    return {"success": True, "session_id": session_id}
