from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin
from app.api.admin_auth import get_current_admin
from app.services import admin_service

router = APIRouter(prefix="/api/admin/admins", tags=["admin"])


class CreateAdminRequest(BaseModel):
    email: str
    password: str
    nickname: str | None = None
    role: str = "admin"


class PasswordRequest(BaseModel):
    password: str


class StatusRequest(BaseModel):
    status: str  # active / disabled


def _admin_dict(a: Admin) -> dict:
    return {
        "id": str(a.id),
        "email": a.email,
        "nickname": a.nickname,
        "role": a.role,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "last_login": a.last_login.isoformat() if a.last_login else None,
    }


@router.get("")
async def list_admins(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.role != "super":
        raise HTTPException(status_code=403, detail="仅超级管理员可管理账号")
    admins = (await db.execute(select(Admin).order_by(Admin.created_at))).scalars().all()
    return {"success": True, "data": [_admin_dict(a) for a in admins]}


@router.post("")
async def create_admin(
    req: CreateAdminRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.role != "super":
        raise HTTPException(status_code=403, detail="仅超级管理员可管理账号")
    if len(req.password) < 6:
        return {"success": False, "message": "密码至少 6 位"}
    existing = await admin_service.get_admin_by_email(db, req.email)
    if existing:
        return {"success": False, "message": "该邮箱已存在"}
    a = Admin(
        email=req.email,
        password_hash=admin_service.hash_password(req.password),
        nickname=req.nickname,
        role=req.role if req.role in ("admin", "super") else "admin",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return {"success": True, "message": "管理员已创建", "admin": _admin_dict(a)}


@router.post("/{admin_id}/status")
async def update_status(
    admin_id: str,
    req: StatusRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.role != "super":
        raise HTTPException(status_code=403, detail="仅超级管理员可管理账号")
    if admin_id == str(admin.id):
        return {"success": False, "message": "不能禁用自己"}
    target = (await db.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if not target:
        return {"success": False, "message": "管理员不存在"}
    target.status = req.status
    await db.commit()
    return {"success": True, "message": "已" + ("禁用" if req.status == "disabled" else "启用")}


@router.post("/{admin_id}/password")
async def reset_password(
    admin_id: str,
    req: PasswordRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.role != "super":
        raise HTTPException(status_code=403, detail="仅超级管理员可管理账号")
    if len(req.password) < 6:
        return {"success": False, "message": "密码至少 6 位"}
    target = (await db.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if not target:
        return {"success": False, "message": "管理员不存在"}
    target.password_hash = admin_service.hash_password(req.password)
    await db.commit()
    return {"success": True, "message": "密码已重置"}
