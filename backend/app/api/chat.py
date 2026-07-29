import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.graph.engine import run_engine
from app.models.conversation import Message, Session
from app.services.soul_service import get_inventory
from app.services.tacit_profile_service import schedule_tacit_refresh

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendRequest(BaseModel):
    message: str
    session_id: str | None = None
    persist_user_message: bool = True
    source_message_id: str | None = None


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"


@router.post("/send")
async def api_send(
    req: SendRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    soul_snapshot = None
    try:
        soul_snapshot = (await get_inventory(user_id, db)).get("current")
    except Exception as e:
        print(f"[chat] load soul snapshot failed: {e}")

    # 1. 自动创建或确认会话
    session_id = req.session_id
    if not session_id:
        sess = Session(user_id=user_id, title="新对话")
        db.add(sess)
        await db.commit()
        await db.refresh(sess)
        session_id = str(sess.id)
    else:
        await db.execute(
            sa_update(Session).where(Session.id == session_id).values(updated_at=datetime.now())
        )

    # 2. 保存用户消息；编辑后重答时复用已编辑的用户消息，避免重复插入一条用户气泡。
    if req.persist_user_message:
        user_msg = Message(session_id=session_id, role="user", content=req.message)
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)
    else:
        if not req.source_message_id:
            raise HTTPException(status_code=400, detail="缺少原始消息")
        msg_result = await db.execute(
            select(Message)
            .join(Session, Message.session_id == Session.id)
            .where(
                Message.id == req.source_message_id,
                Message.session_id == session_id,
                Message.role == "user",
                Session.user_id == user_id,
            )
        )
        user_msg = msg_result.scalar_one_or_none()
        if not user_msg:
            raise HTTPException(status_code=404, detail="消息不存在")

    async def event_stream():
        full_reply = ""
        final_event = None
        yield _sse(
            "message_saved",
            {
                "role": "user",
                "id": str(user_msg.id),
                "session_id": str(session_id),
            },
        )
        if soul_snapshot:
            yield _sse("soul_snapshot", soul_snapshot)
        async for event in run_engine(user_id, req.message, session_id):
            if event.type == "done":
                final_event = event
                continue
            # 收集回复文本
            if event.type == "text_chunk":
                full_reply += event.data.get("text", "")
            yield _sse(event.type, event.data)

        # 3. 消息流结束后保存 agent 回复
        if full_reply:
            metadata = {"soul": soul_snapshot} if soul_snapshot else None
            agent_msg = Message(
                session_id=session_id,
                role="agent",
                content=full_reply,
                metadata_=json.dumps(metadata, ensure_ascii=False) if metadata else None,
            )
            db.add(agent_msg)

            # 首次完整对话后自动更新标题
            sess_result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            sess = sess_result.scalar_one_or_none()
            if sess and not sess.title_auto_set and sess.title == "新对话":
                auto_title = req.message[:30] + ("..." if len(req.message) > 30 else "")
                sess.title = auto_title
                sess.title_auto_set = True
            await db.commit()
            await db.refresh(agent_msg)
            yield _sse(
                "message_saved",
                {
                    "role": "agent",
                    "id": str(agent_msg.id),
                    "session_id": str(session_id),
                },
            )
            try:
                schedule_tacit_refresh(user_id, session_id)
            except Exception as e:
                print(f"[chat] schedule tacit refresh failed: {e}")
        if final_event:
            yield _sse(final_event.type, final_event.data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
