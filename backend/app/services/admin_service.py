import hashlib
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.billing import Admin

settings = get_settings()


def hash_password(password: str) -> str:
    """SHA256 哈希（与用户端一致）"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hash_str: str) -> bool:
    return hash_password(password) == hash_str


def create_admin_token(admin_id: str, email: str) -> str:
    """管理员 access token（token_type=admin_access 与用户端区分）"""
    payload = {
        "sub": admin_id,
        "email": email,
        "token_type": "admin_access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_admin_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("token_type") != "admin_access":
            return None
        return payload
    except JWTError:
        return None


async def get_admin_by_email(db: AsyncSession, email: str) -> Admin | None:
    result = await db.execute(select(Admin).where(Admin.email == email))
    return result.scalar_one_or_none()


async def ensure_default_admin(db: AsyncSession) -> Admin:
    """骨架期兜底：无管理员时创建默认账号（用环境变量可覆盖）"""
    email = os.getenv("ADMIN_EMAIL", "admin@comate.local")
    password = os.getenv("ADMIN_PASSWORD", "admin123456")
    result = await db.execute(select(Admin).where(Admin.email == email))
    admin = result.scalar_one_or_none()
    if not admin:
        admin = Admin(
            email=email,
            password_hash=hash_password(password),
            nickname="超级管理员",
            role="super",
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
    return admin
