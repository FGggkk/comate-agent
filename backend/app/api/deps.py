from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config.settings import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    """从 Authorization header 提取 user_id"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 无效")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
