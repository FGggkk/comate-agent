from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.db.session import run_migrations

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from app.api import auth, chat, souls, memories, interview, reminders, user, sessions
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(souls.router)
    app.include_router(memories.router)
    app.include_router(interview.router)
    app.include_router(reminders.router)
    app.include_router(user.router)
    app.include_router(sessions.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
