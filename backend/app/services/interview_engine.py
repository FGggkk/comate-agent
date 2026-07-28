import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interview import InterviewQuestion, InterviewSession
from app.services.model_gateway import gateway

_session_locks: dict[str, str] = {}


async def start_session(user_id: str, resume: str, target_role: str, company: str, db: AsyncSession) -> dict:
    title = target_role or company or "面试"
    session = InterviewSession(
        user_id=user_id,
        resume_text=resume,
        target_role=target_role,
        target_company=company,
        title=title,
        round_number=1,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    question = await _generate_question(session, db)
    return {
        "session_id": str(session.id),
        "round": session.round_number,
        "question": question,
    }


async def stream_answer(session_id: str, answer: str, db: AsyncSession) -> AsyncGenerator[dict, None]:
    """仅保存回答，不做评估"""
    if _session_locks.get(session_id) == "evaluating":
        yield {"type": "error", "data": {"message": "正在处理中，请稍后"}}
        return
    _session_locks[session_id] = "thinking"

    try:
        q = await _get_pending_question(session_id, db)
        if not q:
            yield {"type": "done", "data": {"message": "所有问题已答完"}}
            return

        q.user_answer = answer
        q.status = "resolved"
        await db.commit()
        _session_locks[session_id] = "feedback_done"

        yield {"type": "answer_saved", "data": {"can_next": True, "can_end": True}}

    finally:
        pass


async def next_question(session_id: str, db: AsyncSession) -> AsyncGenerator[dict, None]:
    """用户主动点下一题"""
    if _session_locks.get(session_id) == "evaluating":
        yield {"type": "error", "data": {"message": "正在评估中，请稍后点下一题"}}
        return

    _session_locks[session_id] = "thinking"

    try:
        session = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
        session = session.scalar_one()

        # 检查该轮已回答数，>=3 则升级
        result = await db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.session_id == session_id,
                InterviewQuestion.round_number == session.round_number,
            )
        )
        answered = [q for q in result.scalars().all() if q.status == "resolved"]

        if len(answered) >= 3:
            if session.round_number < 3:
                session.round_number += 1
                await db.commit()
                yield {"type": "round_change", "data": {"round": session.round_number}}
            else:
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)
                await db.commit()
                yield {"type": "done", "data": {"message": "面试完成！可以查看报告了"}}
                _session_locks.pop(session_id, None)
                return

        # 出一题
        yield {"type": "thinking", "data": {"label": "正在准备下一题…"}}
        q_text = ""
        async for chunk in _stream_with_retry(_generate_question_stream(session, db)):
            q_text += chunk
        yield {"type": "question", "data": {"round": session.round_number, "text": q_text}}
        _session_locks[session_id] = "waiting"

    finally:
        pass


async def end_interview(session_id: str, user_id: str, db: AsyncSession) -> dict:
    """主动结束面试，批量评估所有已回答的问题并打分"""
    session = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = session.scalar_one()

    if str(session.user_id) != user_id:
        return {"success": False, "message": "无权操作"}

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()

    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
        ).order_by(InterviewQuestion.round_number, InterviewQuestion.created_at)
    )
    questions = result.scalars().all()
    answered = [q for q in questions if q.status == "resolved"]

    # 批量评估所有已回答的问题
    evaluations = await _batch_evaluate(answered)

    total_score = 0
    total_max = 0
    for q, ev in zip(answered, evaluations):
        q.evaluation = ev.get("comment", "")
        q.score = ev.get("score", 0)
        q.max_score = ev.get("max_score", 10)
        total_score += q.score
        total_max += q.max_score
    await db.commit()

    overall = round(total_score / total_max * 100) if total_max > 0 else 0

    return {
        "success": True,
        "overall_score": overall,
        "total_score": total_score,
        "total_max": total_max,
        "summary": {
            "total_questions": len(questions),
            "answered": len(answered),
            "target_role": session.target_role,
            "target_company": session.target_company,
            "rounds_completed": session.round_number,
        },
        "questions": [
            {
                "id": str(q.id),
                "round": q.round_number,
                "question": q.question_text,
                "answer": q.user_answer or "",
                "evaluation": q.evaluation or "",
                "score": getattr(q, "score", 0),
                "max_score": getattr(q, "max_score", 10),
            }
            for q in questions
        ],
    }


async def _batch_evaluate(questions: list) -> list[dict]:
    """批量评估所有问题，返回每题得分和评语"""
    if not questions:
        return []

    qa_list = "\n\n".join(
        f"问题{i+1}：\n题目：{q.question_text}\n回答：{q.user_answer}"
        for i, q in enumerate(questions)
    )

    prompt = f"""评估下面的面试回答，每题独立评分。

每题输出格式：得分/满分 评语
满分根据题目重要程度在5-20分之间。

{qa_list}

输出JSON数组：
[{{"score": 8, "max_score": 10, "comment": "得分点... 扣分点..."}}]"""

    try:
        async with asyncio.timeout(45):
            full = ""
            async for chunk in gateway.stream(prompt):
                full += chunk
        import json
        full = full.strip().strip("```json").strip("```").strip()
        results = json.loads(full)
        return results if isinstance(results, list) else []
    except asyncio.TimeoutError:
        print("[batch_evaluate] 超时")
        return [{"score": 5, "max_score": 10, "comment": "评估超时，默认给分。"} for _ in questions]
    except Exception as e:
        print(f"[batch_evaluate] 失败: {e}")
        return [{"score": 0, "max_score": 10, "comment": "评估失败"} for _ in questions]


async def edit_answer(session_id: str, question_id: str, new_answer: str, user_id: str, db: AsyncSession) -> dict:
    """编辑回答，分状态处理"""
    from sqlalchemy import delete as sa_delete

    session = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = session.scalar_one()
    if str(session.user_id) != user_id:
        return {"success": False, "message": "无权操作"}

    q = await db.execute(select(InterviewQuestion).where(InterviewQuestion.id == question_id, InterviewQuestion.session_id == session_id))
    q = q.scalar_one_or_none()
    if not q:
        return {"success": False, "message": "问题不存在"}

    q.user_answer = new_answer
    q.answer_version += 1
    q.evaluation = None
    q.score = None
    q.max_score = None

    if session.status == "in_progress":
        # 删除该题之后所有问题和回答
        await db.execute(
            sa_delete(InterviewQuestion).where(
                InterviewQuestion.session_id == session_id,
                InterviewQuestion.created_at > q.created_at,
            )
        )
        # 清空后续轮次回退
        session.round_number = q.round_number
        await db.commit()

        # 重新生成下一题
        next_q_text = ""
        async for chunk in _stream_with_retry(_generate_question_stream(session, db)):
            next_q_text += chunk

        return {
            "success": True,
            "status": "in_progress",
            "edited_question": {"id": str(q.id), "answer": q.user_answer},
            "next_question": next_q_text,
        }
    else:
        # 已完成 — 仅更新答案，触发重新生成评价
        await db.commit()
        report = await regenerate_report(session_id, db)
        return {
            "success": True,
            "status": "completed",
            "edited_question": {"id": str(q.id), "answer": q.user_answer},
            "report": report,
        }


async def regenerate_report(session_id: str, db: AsyncSession) -> dict:
    """重新生成完整评价文档"""
    session = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = session.scalar_one()

    questions = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
        ).order_by(InterviewQuestion.round_number, InterviewQuestion.created_at)
    )
    questions = questions.scalars().all()
    answered = [q for q in questions if q.status == "resolved" and q.user_answer]

    # 清空旧评分
    for q in questions:
        q.evaluation = None
        q.score = None
        q.max_score = None

    # 批量评估
    evaluations = await _batch_evaluate(answered)

    total_score = 0
    total_max = 0
    for q, ev in zip(answered, evaluations):
        q.evaluation = ev.get("comment", "")
        q.score = ev.get("score", 0)
        q.max_score = ev.get("max_score", 10)
        total_score += q.score
        total_max += q.max_score

    from datetime import timezone
    session.report_version += 1
    session.report_generated_at = datetime.now(timezone.utc)
    await db.commit()

    overall = round(total_score / total_max * 100) if total_max > 0 else 0

    return {
        "overall_score": overall,
        "total_score": total_score,
        "total_max": total_max,
        "report_version": session.report_version,
        "report_generated_at": session.report_generated_at.isoformat() if session.report_generated_at else None,
        "questions": [
            {
                "id": str(q.id),
                "round": q.round_number,
                "question": q.question_text,
                "answer": q.user_answer or "",
                "evaluation": q.evaluation or "",
                "score": q.score or 0,
                "max_score": q.max_score or 10,
            }
            for q in answered
        ],
    }


async def get_report(session_id: str, user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = result.scalar_one()
    if str(session.user_id) != user_id:
        return {"success": False, "message": "无权操作"}
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
        ).order_by(InterviewQuestion.round_number, InterviewQuestion.created_at)
    )
    questions = result.scalars().all()
    answered = [q for q in questions if q.status == "resolved" and q.user_answer]
    total_score = sum(q.score or 0 for q in answered)
    total_max = sum(q.max_score or 10 for q in answered)
    overall = round(total_score / total_max * 100) if total_max > 0 else 0
    return {
        "session_id": str(session.id),
        "target_role": session.target_role,
        "target_company": session.target_company,
        "title": session.title or "",
        "status": session.status,
        "rounds_completed": session.round_number,
        "overall_score": overall,
        "total_score": total_score,
        "total_max": total_max,
        "report_version": session.report_version,
        "report_generated_at": session.report_generated_at.isoformat() if session.report_generated_at else None,
        "questions": [
            {
                "id": str(q.id),
                "round": q.round_number,
                "question": q.question_text,
                "answer": q.user_answer,
                "evaluation": q.evaluation,
                "score": q.score,
                "max_score": q.max_score,
                "status": q.status,
            }
            for q in questions
        ],
    }


# ── 内部辅助 ──

async def _get_pending_question(session_id: str, db: AsyncSession):
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
            InterviewQuestion.status == "pending",
        ).order_by(InterviewQuestion.created_at.asc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _stream_with_retry(agen) -> AsyncGenerator[str, None]:
    last_exc = None
    for attempt in range(3):
        try:
            async with asyncio.timeout(30):
                async for chunk in agen:
                    yield chunk
                return
        except asyncio.TimeoutError:
            last_exc = "超时"
            if attempt < 2:
                continue
        except Exception as e:
            last_exc = str(e)
            if attempt < 2:
                await asyncio.sleep(1)
                continue
        break
    yield f"\n\n[生成超时，请重试]"


async def _evaluate_answer_stream(question: str, answer: str) -> AsyncGenerator[str, None]:
    prompt = f"""面试问题：{question}
候选人回答：{answer}

请用三段式精简评估（总共不超过150字）：
1. 优点（一句话）
2. 改进点（一句话）
3. 示例或建议（一句话）

只输出以上三段，不要多余内容。"""
    async for chunk in gateway.stream(prompt):
        yield chunk


async def _generate_question_stream(session: InterviewSession, db: AsyncSession) -> AsyncGenerator[str, None]:
    # 获取之前所有 Q&A 上下文
    prev_qa = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session.id,
        ).order_by(InterviewQuestion.created_at.asc()).limit(10)
    )
    prev_questions = prev_qa.scalars().all()
    context = "\n".join(
        f"之前问题：{q.question_text}\n候选人回答：{q.user_answer or '（未回答）'}"
        for q in prev_questions if q.user_answer
    )

    prompt = f"""你是一个面试官，正在面试{session.target_role}岗位（{session.target_company}）。
简历：{session.resume_text}

面试历史：
{context if context else '（面试刚开始）'}

第 {session.round_number} 轮面试。请只出一道题，不要出多道。
要求：基于前面的对话自然延续，不要重复已问过的问题，让整场面试像真实对话一样连贯。"""
    if session.round_number == 1:
        prompt += "\n从简单的自我介绍或项目经历切入。"
    elif session.round_number == 2:
        prompt += "\n根据上一轮的回答深入追问，考察技术深度和项目细节。"
    else:
        prompt += "\n基于前两轮表现，出一道综合性的场景题，考察决策能力和综合素养。"

    reply_buffer = ""
    async for chunk in gateway.stream(prompt):
        reply_buffer += chunk
        yield chunk

    question = reply_buffer.strip().strip('"').strip("'")
    q = InterviewQuestion(
        session_id=session.id,
        round_number=session.round_number,
        question_text=question,
    )
    db.add(q)
    await db.commit()


async def _generate_question(session: InterviewSession, db: AsyncSession) -> str:
    result = ""
    async for chunk in _generate_question_stream(session, db):
        result += chunk
    return result.strip().strip('"').strip("'")


# ── 兼容旧接口 ──

async def answer_question(session_id: str, answer: str, user_id: str, db: AsyncSession) -> dict:
    q = await _get_pending_question(session_id, db)
    if not q:
        return {"done": True, "message": "所有问题已答完"}
    from app.models.interview import InterviewSession
    sess = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    sess = sess.scalar_one()
    if str(sess.user_id) != user_id:
        return {"success": False, "message": "无权操作"}
    q.user_answer = answer
    eval_text = ""
    try:
        async for chunk in _stream_with_retry(_evaluate_answer_stream(q.question_text, answer)):
            eval_text += chunk
    except Exception:
        eval_text = "评估生成失败"
    q.evaluation = eval_text
    q.status = "resolved"
    await db.commit()
    return {"done": False, "evaluation": eval_text}
