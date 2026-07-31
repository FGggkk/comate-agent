from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config.settings import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def get_user_id_from_token(token: str) -> str:
    """校验 JWT 并返回 user_id，供 HTTP 与 WebSocket 入口共用。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 无效")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    """从 Authorization header 提取 user_id"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")

    return get_user_id_from_token(credentials.credentials)
