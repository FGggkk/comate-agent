from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services.interview_engine import answer_question, get_report, start_session

router = APIRouter(prefix="/api/interview", tags=["interview"])


class StartRequest(BaseModel):
    resume_text: str = ""
    target_role: str = ""
    target_company: str = ""


class AnswerRequest(BaseModel):
    answer: str


@router.post("/start")
async def api_start(req: StartRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await start_session(user_id, req.resume_text, req.target_role, req.target_company, db)


@router.post("/{session_id}/answer")
async def api_answer(session_id: str, req: AnswerRequest, db: AsyncSession = Depends(get_db)):
    return await answer_question(session_id, req.answer, db)


@router.get("/{session_id}/report")
async def api_report(session_id: str, db: AsyncSession = Depends(get_db)):
    return await get_report(session_id, db)
