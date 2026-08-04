import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import fail, ok
from app.db.session import get_db
from app.models.conversation import Message, Session
from app.models.user import User
from app.plugins.company_knowledge.answer_service import NO_EVIDENCE_REPLY, stream_company_knowledge_answer
from app.plugins.company_knowledge.registry import get_knowledge_type, is_query_enabled, list_knowledge_types
from app.plugins.company_knowledge.retriever import RetrievalError, retrieve_company_knowledge
from app.plugins.company_knowledge.schemas import CompanyKnowledgeQueryRequest
from app.plugins.company_knowledge.service import (
    CompanyKnowledgeServiceError,
    ensure_company_knowledge_session,
    save_company_knowledge_answer,
    save_company_knowledge_user_message,
)
from app.services.tacit_profile_service import schedule_tacit_refresh


router = APIRouter(prefix="/api/company-knowledge", tags=["company-knowledge"])


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"


async def is_rag_enabled(db: AsyncSession, user_id: str) -> bool:
    user = await db.get(User, user_id)
    return bool(user and user.status == "active" and user.rag_enabled)


def _message_to_dict(message: Message) -> dict:
    try:
        metadata = json.loads(message.metadata_ or "{}")
    except json.JSONDecodeError:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "metadata": metadata,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


@router.get("/types")
async def list_types(user_id: str = Depends(get_current_user)):
    """返回所有已注册资料类型，供前端按可用状态组织入口。"""
    return ok({"items": list_knowledge_types()})


@router.get("/messages")
async def list_company_knowledge_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """仅回放当前用户在 RAG 悬浮会话中的消息，不混入普通聊天时间线。"""
    if not await is_rag_enabled(db, user_id):
        return JSONResponse(
            status_code=403,
            content=fail("当前用户未启用 RAG 功能", {"code": "rag_disabled"}),
        )
    session = (
        await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user_id))
    ).scalar_one_or_none()
    if not session:
        return fail("会话不存在")
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.msg_type == "company_knowledge")
        .order_by(Message.created_at.asc())
        .limit(100)
    )
    return ok({"session_id": str(session.id), "messages": [_message_to_dict(item) for item in result.scalars()]})


@router.post("/query")
async def query_company_knowledge(
    req: CompanyKnowledgeQueryRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """仅基于已发布且生效的公司资料回答，并把来源快照写入当前会话。"""
    if not await is_rag_enabled(db, user_id):
        return JSONResponse(
            status_code=403,
            content=fail("当前用户未启用 RAG 功能", {"code": "rag_disabled"}),
        )
    knowledge_type = get_knowledge_type(req.knowledge_type)
    if not knowledge_type or not is_query_enabled(req.knowledge_type):
        return fail(
            f"{knowledge_type.label if knowledge_type else '该资料类型'}暂未启用查询",
            {"code": "knowledge_type_disabled", "knowledge_type": req.knowledge_type},
        )
    question = req.message.strip()
    if not question:
        return fail("问题不能为空", {"code": "empty_question"})

    try:
        session = await ensure_company_knowledge_session(db, user_id, req.session_id)
        user_message = await save_company_knowledge_user_message(
            db,
            session=session,
            message=question,
            knowledge_type=req.knowledge_type,
            input_mode=req.input_mode,
        )
    except CompanyKnowledgeServiceError as exc:
        return fail(str(exc), {"code": "company_knowledge_session_error"})

    async def event_stream():
        yield _sse(
            "message_saved",
            {"role": "user", "id": str(user_message.id), "session_id": str(session.id)},
        )
        citations: list[dict] = []
        answer = ""
        try:
            chunks = await retrieve_company_knowledge(question, req.knowledge_type, db)
        except RetrievalError:
            # 检索不可用时不能退回到通用聊天模型，避免给出没有制度依据的回答。
            answer = "暂时无法完成制度检索，请稍后再试。"
            yield _sse("error", {"message": answer, "code": "knowledge_retrieval_failed"})
        else:
            citations = [chunk.to_citation() for chunk in chunks]
            if not chunks:
                answer = NO_EVIDENCE_REPLY
                yield _sse("text_chunk", {"text": answer})
            else:
                yield _sse("sources", {"items": citations})
                try:
                    async for text in stream_company_knowledge_answer(question, chunks):
                        answer += text
                        yield _sse("text_chunk", {"text": text})
                except Exception:
                    answer = "暂时无法生成制度答复，请稍后再试。"
                    yield _sse("error", {"message": answer, "code": "knowledge_answer_failed"})

        if not answer:
            answer = "暂时无法生成制度答复，请稍后再试。"
            yield _sse("error", {"message": answer, "code": "knowledge_answer_empty"})

        try:
            answer_message = await save_company_knowledge_answer(
                db,
                session=session,
                question=question,
                answer=answer,
                knowledge_type=req.knowledge_type,
                citations=citations,
            )
            yield _sse(
                "message_saved",
                {"role": "agent", "id": str(answer_message.id), "session_id": str(session.id)},
            )
            schedule_tacit_refresh(user_id, str(session.id))
        except Exception:
            yield _sse("error", {"message": "回答已生成，但保存会话失败。", "code": "knowledge_save_failed"})
        yield _sse("done", {"session_id": str(session.id), "citations": citations})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
