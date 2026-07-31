from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin
from app.services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _admin_to_dict(a: Admin) -> dict:
    return {
        "id": str(a.id),
        "email": a.email,
        "nickname": a.nickname,
        "role": a.role,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


async def get_current_admin(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """管理员鉴权依赖：校验 Bearer admin token + 账号状态"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    payload = admin_service.verify_admin_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    result = await db.execute(select(Admin).where(Admin.id == payload.get("sub")))
    admin = result.scalar_one_or_none()
    if not admin or admin.status != "active":
        raise HTTPException(status_code=401, detail="账号不可用")
    return admin


@router.post("/auth/login")
async def admin_login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await admin_service.get_admin_by_email(db, req.email)
    if not admin or not admin_service.verify_password(req.password, admin.password_hash):
        return {"success": False, "message": "邮箱或密码错误"}
    if admin.status != "active":
        return {"success": False, "message": "账号已禁用"}
    admin.last_login = datetime.now(timezone.utc)
    await db.commit()
    token = admin_service.create_admin_token(str(admin.id), admin.email)
    return {"success": True, "token": token, "admin": _admin_to_dict(admin)}


@router.get("/auth/me")
async def admin_me(admin: Admin = Depends(get_current_admin)):
    return {"success": True, "admin": _admin_to_dict(admin)}
