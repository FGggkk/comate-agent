import hashlib
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.services.email_service import generate_code, send_verification_code

settings = get_settings()
CODE_TTL_MINUTES = 5
RESEND_INTERVAL_SECONDS = 60


def _hash_password(password: str) -> str:
    """SHA256 哈希（v1 简化版，后续可换成 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, hash_str: str) -> bool:
    return _hash_password(password) == hash_str


async def send_code(email: str, db: AsyncSession) -> dict:
    # 检查 60 秒内是否已发送
    since = datetime.now(timezone.utc) - timedelta(seconds=RESEND_INTERVAL_SECONDS)
    result = await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.created_at > since,
            VerificationCode.used == False,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"success": False, "message": "请 60 秒后再试"}

    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)

    vc = VerificationCode(email=email, code=code, expires_at=expires_at)
    db.add(vc)
    await db.commit()

    try:
        await send_verification_code(email, code)
        return {"success": True, "message": "验证码已发送"}
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return {"success": False, "message": f"邮件发送失败: {e}"}


async def register(email: str, code: str, password: str, db: AsyncSession) -> dict:
    """验证码校验 + 注册（设置密码）"""
    # 校验验证码
    result = await db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.code == code,
            VerificationCode.used == False,
            VerificationCode.expires_at > datetime.now(timezone.utc),
        )
    )
    vc = result.scalar_one_or_none()
    if not vc:
        return {"success": False, "message": "验证码无效或已过期"}

    vc.used = True

    # 检查用户是否存在
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = False
    if not user:
        user = User(email=email, password_hash=_hash_password(password))
        db.add(user)
        is_new = True
    else:
        # 已有账号，更新密码
        user.password_hash = _hash_password(password)

    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    token = _create_token(str(user.id), email)
    refresh_token = _create_refresh_token(str(user.id), email)
    return {
        "success": True,
        "token": token,
        "refresh_token": refresh_token,
        "expires_in": settings.jwt_expire_hours * 3600,
        "is_new_user": is_new,
        "onboarding_status": user.onboarding_status,
    }


async def login(email: str, password: str, db: AsyncSession) -> dict:
    """邮箱 + 密码登录"""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        return {"success": False, "message": "账号不存在或未注册"}

    if not _verify_password(password, user.password_hash):
        return {"success": False, "message": "密码错误"}

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    token = _create_token(str(user.id), email)
    refresh_token = _create_refresh_token(str(user.id), email)
    return {
        "success": True,
        "token": token,
        "refresh_token": refresh_token,
        "expires_in": settings.jwt_expire_hours * 3600,
        "is_new_user": False,
        "onboarding_status": user.onboarding_status,
    }


def _create_token(user_id: str, email: str) -> str:
    """短期 access token（默认 72 小时）"""
    payload = {
        "sub": user_id,
        "email": email,
        "token_type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _create_refresh_token(user_id: str, email: str) -> str:
    """长期 refresh token（默认 7 天），仅用于换取新的 access token"""
    payload = {
        "sub": user_id,
        "email": email,
        "token_type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def refresh_access_token(refresh_token: str) -> dict | None:
    """用 refresh token 换取新的 access token"""
    payload = verify_token(refresh_token)
    if not payload or payload.get("token_type") != "refresh":
        return None
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        return None
    new_access = _create_token(user_id, email)
    return {
        "access_token": new_access,
        "expires_in": settings.jwt_expire_hours * 3600,
    }


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
