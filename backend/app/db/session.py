from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


MIGRATION_SQL = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(64)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding vector(1536)",
]


async def run_migrations():
    """应用启动时自动执行数据库迁移"""
    try:
        async with engine.begin() as conn:
            for stmt in MIGRATION_SQL:
                try:
                    await conn.execute(text(stmt))
                    print(f"[migrate] OK: {stmt[:60]}")
                except Exception as e:
                    print(f"[migrate] SKIP ({e}): {stmt[:60]}")
        print("[migrate] 数据库迁移完成")
    except Exception as e:
        print(f"[migrate] 迁移失败（可忽略）: {e}")
