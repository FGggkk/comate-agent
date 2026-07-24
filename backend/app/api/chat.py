import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.graph.engine import run_engine
from app.models.conversation import Message, Session

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/send")
async def api_send(
    req: SendRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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

    # 2. 保存用户消息
    user_msg = Message(session_id=session_id, role="user", content=req.message)
    db.add(user_msg)
    await db.commit()

    async def event_stream():
        full_reply = ""
        async for event in run_engine(user_id, req.message, session_id):
            # 收集回复文本
            if event.type == "text_chunk":
                full_reply += event.data.get("text", "")
            yield f"data: {json.dumps({'type': event.type, 'data': event.data}, ensure_ascii=False)}\n\n"

        # 3. 消息流结束后保存 agent 回复
        if full_reply:
            agent_msg = Message(session_id=session_id, role="agent", content=full_reply)
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

    return StreamingResponse(event_stream(), media_type="text/event-stream")
