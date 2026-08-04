import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interview import InterviewQuestion, InterviewSession
from app.services.model_gateway import gateway

_session_locks: dict[str, str] = {}


DIFFICULTY_ROUNDS = {"easy": 1, "medium": 2, "hard": 3}

INTERVIEW_TYPE_PROMPTS = {
    "tech": "你是一个技术面试官，正在对候选人进行技术深度面试。重点考察技术原理、架构设计、代码能力和最佳实践。",
    "behavior": "你是一个HR面试官，正在对候选人进行行为面试。重点考察团队协作、冲突处理、领导力和职业规划。",
    "project": "你是一个技术负责人，正在深挖候选人的项目经历。重点考察项目难点、技术选型、个人贡献和复盘反思。",
    "stress": "你是一个压力面试官，节奏紧凑、连续追问。考察候选人的抗压能力、思维速度和应变能力。",
    "comprehensive": "你是一个综合面试官，从基础到项目到软技能全面考察候选人。",
}


async def start_session(user_id: str, resume: str, target_role: str, company: str, interview_type: str = "comprehensive", difficulty: str = "medium", db: AsyncSession = None) -> dict:
    max_rounds = DIFFICULTY_ROUNDS.get(difficulty, 2)
    title = target_role or company or "面试"
    session = InterviewSession(
        user_id=user_id,
        resume_text=resume,
        target_role=target_role,
        target_company=company,
        interview_type=interview_type,
        difficulty=difficulty,
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
        max_rounds = DIFFICULTY_ROUNDS.get(session.difficulty or "medium", 2)

        if len(answered) >= 3:
            if session.round_number < max_rounds:
                session.round_number += 1
                await db.commit()
                yield {"type": "round_change", "data": {"round": session.round_number, "max_rounds": max_rounds}}
            else:
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)
                await db.commit()
                yield {"type": "done", "data": {"message": "面试完成！可以查看报告了"}}
                _session_locks.pop(session_id, None)
                return

        # 如果已完成但还没 return（防御性检查）
        if session.status == "completed":
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
    dim_sums = {"tech_depth": 0, "communication": 0, "logic": 0, "project_exp": 0, "adaptability": 0}
    dim_counts = {"tech_depth": 0, "communication": 0, "logic": 0, "project_exp": 0, "adaptability": 0}
    for q, ev in zip(answered, evaluations):
        q.evaluation = ev.get("comment", "")
        q.score = ev.get("score", 0)
        q.max_score = ev.get("max_score", 10)
        total_score += q.score
        total_max += q.max_score
        dims = ev.get("dimensions", {})
        for key in dim_sums:
            val = dims.get(key)
            if isinstance(val, (int, float)):
                dim_sums[key] += val
                dim_counts[key] += 1
    await db.commit()

    overall = round(total_score / total_max * 100) if total_max > 0 else 0
    dimension_scores = {}
    for key in dim_sums:
        dimension_scores[key] = round(dim_sums[key] / dim_counts[key], 1) if dim_counts[key] > 0 else 0

    session.dimension_scores = dimension_scores
    await db.commit()

    return {
        "success": True,
        "overall_score": overall,
        "total_score": total_score,
        "total_max": total_max,
        "dimension_scores": dimension_scores,
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

所有题目的满分之和必须等于100分，每题根据重要程度分配不同的满分（重要题目满分高，次要题目满分低）。

每题输出 JSON 对象，格式：
{{
  "score": 分数,
  "max_score": 满分,
  "comment": "评语",
  "dimensions": {{
    "tech_depth": 0-10,
    "communication": 0-10,
    "logic": 0-10,
    "project_exp": 0-10,
    "adaptability": 0-10
  }}
}}

注意：所有题的 max_score 相加必须等于100！
各维度满分10分，评估候选人在该题表现出的能力。

{qa_list}

输出JSON数组：
[{{"score": 15, "max_score": 30, "comment": "得分点... 扣分点...", "dimensions": {{"tech_depth": 7, "communication": 8, "logic": 6, "project_exp": 5, "adaptability": 4}}}}]"""

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
        "dimension_scores": session.dimension_scores or {},
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

    # 面试类型提示
    type_hint = INTERVIEW_TYPE_PROMPTS.get(session.interview_type or "comprehensive", INTERVIEW_TYPE_PROMPTS["comprehensive"])
    max_rounds = DIFFICULTY_ROUNDS.get(session.difficulty or "medium", 2)

    prompt = f"""你是一个面试官，正在面试{session.target_role}岗位（{session.target_company}）。
{type_hint}

简历：{session.resume_text}

面试历史：
{context if context else '（面试刚开始）'}

第 {session.round_number} 轮面试（共 {max_rounds} 轮）。请只出一道题，不要出多道。
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
