from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.cos_service import upload_avatar

router = APIRouter(prefix="/api/user", tags=["user"])


class UpdateProfileRequest(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None


@router.get("/me")
async def get_profile(user_id: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"success": False, "message": "用户不存在"}

    return {
        "success": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "rag_enabled": bool(user.rag_enabled),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    }


@router.put("/me")
async def update_profile(
    req: UpdateProfileRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"success": False, "message": "用户不存在"}

    if req.nickname is not None:
        user.nickname = req.nickname
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url

    await db.commit()
    await db.refresh(user)

    return {
        "success": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "rag_enabled": bool(user.rag_enabled),
        },
    }


MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/avatar")
async def upload_avatar_api(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传头像文件 → COS → 更新 avatar_url"""
    if not file.content_type or not file.content_type.startswith("image/"):
        return {"success": False, "message": "请上传图片文件"}

    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        return {"success": False, "message": "图片大小不能超过 5MB"}

    url = upload_avatar(content, file.filename or "avatar.png", user_id)
    if not url:
        return {"success": False, "message": "头像上传失败，请检查 COS 配置"}

    # 更新用户 avatar_url
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.avatar_url = url
        await db.commit()
        await db.refresh(user)

    return {
        "success": True,
        "avatar_url": url,
        "user": {
            "id": str(user.id) if user else "",
            "email": user.email if user else "",
            "nickname": user.nickname if user else "",
            "avatar_url": url,
            "rag_enabled": bool(user.rag_enabled) if user else False,
        },
    }
