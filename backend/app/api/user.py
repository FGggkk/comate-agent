from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User

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
        },
    }
