import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.graph.engine import run_engine

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/send")
async def api_send(req: SendRequest, user_id: str = Depends(get_current_user)):
    async def event_stream():
        async for event in run_engine(user_id, req.message, req.conversation_id):
            yield f"data: {json.dumps({'type': event.type, 'data': event.data}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
