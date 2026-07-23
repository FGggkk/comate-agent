from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview import InterviewQuestion, InterviewSession
from app.services.model_gateway import gateway


async def start_session(user_id: str, resume: str, target_role: str, company: str, db: AsyncSession) -> dict:
    session = InterviewSession(
        user_id=user_id,
        resume_text=resume,
        target_role=target_role,
        target_company=company,
        round_number=1,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 生成第一题
    question = await _generate_question(session, db)
    return {
        "session_id": str(session.id),
        "round": session.round_number,
        "question": question,
    }


async def answer_question(session_id: str, answer: str, db: AsyncSession) -> dict:
    # 获取当前未回答的问题
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
            InterviewQuestion.status == "pending",
        ).order_by(InterviewQuestion.created_at.asc()).limit(1)
    )
    q = result.scalar_one_or_none()
    if not q:
        return {"done": True, "message": "所有问题已答完"}

    # 保存答案 + 评估
    q.user_answer = answer
    evaluation = await _evaluate_answer(q.question_text, answer)
    q.evaluation = evaluation
    q.status = "resolved"

    await db.commit()

    # 获取 session
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = result.scalar_one()

    # 检查是否完成本轮的足够题数
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
            InterviewQuestion.round_number == session.round_number,
        )
    )
    questions = result.scalars().all()
    answered = [q for q in questions if q.status == "resolved"]

    if len(answered) >= 3:
        # 进入下一轮或结束
        if session.round_number < 3:
            session.round_number += 1
            await db.commit()
            next_q = await _generate_question(session, db)
            return {
                "done": False,
                "round": session.round_number,
                "question": next_q,
                "evaluation": evaluation,
            }
        else:
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"done": True, "message": "面试完成！可以查看报告了", "evaluation": evaluation}

    # 继续出下一题
    next_q = await _generate_question(session, db)
    return {
        "done": False,
        "round": session.round_number,
        "question": next_q,
        "evaluation": evaluation,
    }


async def get_report(session_id: str, db: AsyncSession) -> dict:
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = result.scalar_one()

    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.session_id == session_id,
        ).order_by(InterviewQuestion.round_number, InterviewQuestion.created_at)
    )
    questions = result.scalars().all()

    return {
        "session_id": str(session.id),
        "target_role": session.target_role,
        "target_company": session.target_company,
        "status": session.status,
        "rounds_completed": session.round_number,
        "questions": [
            {
                "round": q.round_number,
                "question": q.question_text,
                "answer": q.user_answer,
                "evaluation": q.evaluation,
                "status": q.status,
            }
            for q in questions
        ],
    }


async def _generate_question(session: InterviewSession, db: AsyncSession) -> str:
    prompt = f"""你是一个面试官，正在面试一位{session.target_role}岗位的候选人（目标公司：{session.target_company}）。

候选人的简历：
{session.resume_text}

当前是第 {session.round_number} 轮面试。

"""
    if session.round_number == 1:
        prompt += "请出第一道面试题，从自我介绍或项目经验开始。"
    elif session.round_number == 2:
        # 获取第一轮未解决的问题
        result = await db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.session_id == session.id,
                InterviewQuestion.round_number == 1,
            )
        )
        prev = result.scalars().all()
        weak_areas = [q.question_text for q in prev if q.status == "pending"]
        if weak_areas:
            prompt += f"候选人上一轮在以下问题上表现不足，请重点考察：{', '.join(weak_areas[:3])}"
        else:
            prompt += "请出更有深度的问题，考察候选人的技术深度和项目理解。"
    else:
        prompt += "这是压力面试轮。请出一道有挑战性的场景题，追问候选人的决策过程和取舍逻辑。"

    reply = await gateway.chat(prompt)
    # 清理回复
    question = reply.strip().strip('"').strip("'")

    q = InterviewQuestion(
        session_id=session.id,
        round_number=session.round_number,
        question_text=question,
    )
    db.add(q)
    await db.commit()

    return question


async def _evaluate_answer(question: str, answer: str) -> str:
    prompt = f"""面试问题：{question}

候选人的回答：{answer}

请从以下维度评估（每个维度 1-5 分）：
1. 内容完整性
2. 逻辑清晰度
3. 与岗位匹配度

请用一两句话给出评价和改进建议。"""
    try:
        evaluation = await gateway.chat(prompt)
        return evaluation.strip()
    except Exception:
        return "评估生成失败，请人工复核。"
