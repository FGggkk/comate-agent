import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok, fail
from app.db.session import get_db
from app.services import billing_service
from app.services.interview_engine import (
    answer_question,
    edit_answer,
    end_interview,
    get_report,
    next_question,
    start_session,
    stream_answer,
)

router = APIRouter(prefix="/api/interview", tags=["interview"])


class StartRequest(BaseModel):
    resume_text: str = ""
    target_role: str = ""
    target_company: str = ""
    interview_type: str = "comprehensive"  # tech/behavior/project/stress/comprehensive
    difficulty: str = "medium"  # easy/medium/hard


class AnswerRequest(BaseModel):
    answer: str

class EditAnswerRequest(BaseModel):
    question_id: str
    answer: str

class RenameRequest(BaseModel):
    title: str

class HintRequest(BaseModel):
    question: str

class EditAnswerBody(BaseModel):
    new_answer: str


def _sse(event_type: str, data: dict) -> str:
    payload = {
        "type": event_type,
        "data": data,
        "event_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/start")
async def api_start(req: StartRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok(await start_session(user_id, req.resume_text, req.target_role, req.target_company, req.interview_type, req.difficulty, db))


@router.post("/{session_id}/answer")
async def api_answer(session_id: str, req: AnswerRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    # 计费：面试提问
    bill = await billing_service.consume(db, user_id, "interview_question", ref_type="interview", ref_id=session_id, note="面试提问")
    if bill.get("insufficient"):
        return fail(bill["message"])
    result = await answer_question(session_id, req.answer, user_id, db)
    return ok(result) if "success" not in result else result


@router.post("/{session_id}/answer/stream")
async def api_answer_stream(session_id: str, req: AnswerRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    # 计费：面试提问（流式，先扣费再开流）
    bill = await billing_service.consume(db, user_id, "interview_question", ref_type="interview", ref_id=session_id, note="面试提问")
    if bill.get("insufficient"):
        return fail(bill["message"])
    async def event_stream():
        yield _sse("init", {"session_id": session_id})
        async for event in stream_answer(session_id, req.answer, db):
            yield _sse(event["type"], event["data"])
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/next")
async def api_next(session_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    """用户主动点下一题"""
    async def event_stream():
        yield _sse("init", {"session_id": session_id})
        async for event in next_question(session_id, db):
            yield _sse(event["type"], event["data"])
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/end")
async def api_end(session_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    """主动结束面试"""
    # 计费：面试报告
    await billing_service.consume(db, user_id, "interview_report", ref_type="interview", ref_id=session_id, note="面试报告")
    return await end_interview(session_id, user_id, db)


@router.get("")
async def api_list_sessions(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.interview import InterviewSession
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.user_id == user_id).order_by(InterviewSession.created_at.desc()).limit(20)
    )
    sessions = result.scalars().all()
    return ok({
        "sessions": [
            {
                "id": str(s.id),
                "target_role": s.target_role,
                "target_company": s.target_company,
                "title": s.title or "",
                "status": s.status,
                "round_number": s.round_number,
                "difficulty": s.difficulty or "medium",
                "max_rounds": {"easy": 1, "medium": 2, "hard": 3}.get(s.difficulty or "medium", 2),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ]
    })


@router.put("/{session_id}/answer/{question_id}")
async def api_edit_single_answer(
    session_id: str,
    question_id: str,
    req: EditAnswerBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """编辑回答（进行中/已完成分状态处理）"""
    return await edit_answer(session_id, question_id, req.new_answer, user_id, db)


@router.put("/{session_id}")
async def api_rename(
    session_id: str,
    req: RenameRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """重命名面试记录"""
    from sqlalchemy import select, update
    from app.models.interview import InterviewSession
    r = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id))
    s = r.scalar_one_or_none()
    if not s:
        return {"success": False}
    s.title = req.title
    await db.commit()
    return {"success": True, "title": req.title}


@router.delete("/{session_id}")
async def api_delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """删除面试记录"""
    from sqlalchemy import select, delete as sa_delete
    from app.models.interview import InterviewSession, InterviewQuestion
    sess = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id))
    if not sess.scalar_one_or_none():
        return {"success": False, "message": "无权操作"}
    await db.execute(sa_delete(InterviewQuestion).where(InterviewQuestion.session_id == session_id))
    await db.execute(sa_delete(InterviewSession).where(InterviewSession.id == session_id))
    await db.commit()
    return {"success": True}


@router.put("/{session_id}/answer")
async def api_edit_answer(
    session_id: str,
    req: EditAnswerRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """编辑历史面试的回答"""
    from sqlalchemy import select, update
    from app.models.interview import InterviewQuestion, InterviewSession
    # 验证会话归属
    sess = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id))
    if not sess.scalar_one_or_none():
        return {"success": False, "message": "无权操作"}
    await db.execute(
        update(InterviewQuestion).where(InterviewQuestion.id == req.question_id).values(user_answer=req.answer)
    )
    await db.commit()
    return {"success": True}


@router.get("/{session_id}/report")
async def api_report(session_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    result = await get_report(session_id, user_id, db)
    return ok(result) if "success" not in result else result


@router.post("/{session_id}/hint")
async def api_hint(session_id: str, req: HintRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    # 计费：思路提示
    bill = await billing_service.consume(db, user_id, "reroll_hint", ref_type="interview", ref_id=session_id, note="思路提示")
    if bill.get("insufficient"):
        return fail(bill["message"])
    from app.services.model_gateway import gateway
    prompt = f"""你是面试辅导教练。用户正在面试，遇到了这个问题：

{req.question}

请给出回答思路引导（不是标准答案），包括：
1. 这个问题在考察什么能力
2. 可以从哪几个角度回答
3. 建议用什么结构组织回答

控制在200字以内，简洁实用。"""
    hint = ""
    async for chunk in gateway.stream(prompt):
        hint += chunk
    return ok({"hint": hint.strip()})


@router.post("/{session_id}/reroll")
async def api_reroll(session_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    """重新生成当前轮的最新一道 pending 题"""
    # 计费：重出题
    bill = await billing_service.consume(db, user_id, "reroll_hint", ref_type="interview", ref_id=session_id, note="重出题")
    if bill.get("insufficient"):
        return fail(bill["message"])
    from sqlalchemy import select, delete
    from app.models.interview import InterviewSession, InterviewQuestion
    sess = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id))
    sess_obj = sess.scalar_one_or_none()
    if not sess_obj:
        return fail("无权操作")
    latest = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
            InterviewQuestion.round_number == sess_obj.round_number,
            InterviewQuestion.status == "pending",
        ).order_by(InterviewQuestion.created_at.desc()).limit(1)
    )
    q = latest.scalar_one_or_none()
    if not q:
        return ok({"message": "没有可重出的题目"})
    await db.execute(delete(InterviewQuestion).where(InterviewQuestion.id == q.id))
    await db.commit()
    from app.services.interview_engine import _generate_question
    new_q = await _generate_question(sess_obj, db)
    return ok({"question": new_q})
