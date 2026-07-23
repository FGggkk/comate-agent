from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import login, register, send_code

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SendCodeRequest(BaseModel):
    email: str


class RegisterRequest(BaseModel):
    email: str
    code: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/send-code")
async def api_send_code(req: SendCodeRequest, db: AsyncSession = Depends(get_db)):
    return await send_code(req.email, db)


@router.post("/register")
async def api_register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register(req.email, req.code, req.password, db)


@router.post("/login")
async def api_login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login(req.email, req.password, db)
