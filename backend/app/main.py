import sys
from contextlib import asynccontextmanager

# Windows 下 stdout/stderr 默认 GBK，遇到 emoji 等字符会抛 UnicodeEncodeError，
# 全局改为 UTF-8 + errors=replace 兜底
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.db.session import async_session_factory, run_migrations

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    # 骨架期兜底：确保存在一个默认管理员账号
    from app.services import admin_service
    async with async_session_factory() as db:
        await admin_service.ensure_default_admin(db)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由

    from app.api import auth, chat, souls, memories, interview, reminders, user, sessions, messages, finance, travel, shopping, voice, admin_auth, admin_dashboard, admin_codes, admin_users, admin_settings, admin_stats, admin_admins, admin_souls, billing

    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(souls.router)
    app.include_router(memories.router)
    app.include_router(interview.router)
    app.include_router(reminders.router)
    app.include_router(user.router)
    app.include_router(sessions.router)
    app.include_router(messages.router)
    app.include_router(finance.router)
    app.include_router(travel.router)
    app.include_router(shopping.router)
    app.include_router(voice.router)
    app.include_router(admin_auth.router)
    app.include_router(admin_dashboard.router)
    app.include_router(admin_codes.router)
    app.include_router(admin_users.router)
    app.include_router(admin_settings.router)
    app.include_router(admin_stats.router)
    app.include_router(admin_admins.router)
    app.include_router(admin_souls.router)
    app.include_router(billing.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        print(f"[unhandled] {exc}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "服务器内部错误", "detail": str(exc) if settings.debug else None},
        )

    return app


app = create_app()
