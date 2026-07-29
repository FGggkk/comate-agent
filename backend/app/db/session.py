from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug, pool_timeout=10, connect_args={"timeout": 10})
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
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS event_at TIMESTAMPTZ",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS observed_count INTEGER DEFAULT 0",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS last_observed_at TIMESTAMPTZ",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(160)",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS review_after TIMESTAMPTZ",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS scope VARCHAR(16) DEFAULT 'global'",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS topic_tags JSONB DEFAULT '[]'",
    "UPDATE memory_items SET event_at = (content->>'event_at')::timestamptz WHERE event_at IS NULL AND content ? 'event_at' AND content->>'event_at' ~ '^\\d{4}-\\d{2}-\\d{2}'",
    "UPDATE memory_items SET expires_at = (content->>'expires_at')::timestamptz WHERE expires_at IS NULL AND content ? 'expires_at' AND content->>'expires_at' ~ '^\\d{4}-\\d{2}-\\d{2}'",
    "UPDATE memory_items SET scope = content->>'scope' WHERE content ? 'scope' AND content->>'scope' IN ('global', 'topic', 'session', 'ephemeral')",
    "UPDATE memory_items SET topic_tags = content->'topic_tags' WHERE content ? 'topic_tags' AND jsonb_typeof(content->'topic_tags') = 'array'",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_expiry ON memory_items (user_id, expires_at) WHERE status = 'active' AND expires_at IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_review ON memory_items (user_id, review_after) WHERE status = 'active' AND review_after IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_dedupe ON memory_items (user_id, layer, memory_type, dedupe_key) WHERE status = 'active' AND dedupe_key IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_scope ON memory_items (user_id, layer, scope) WHERE status = 'active'",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_topic_tags ON memory_items USING GIN (topic_tags)",
    "CREATE TABLE IF NOT EXISTS memory_observations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), memory_id UUID NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE, user_id UUID NOT NULL REFERENCES users(id), source_type VARCHAR(32) DEFAULT 'chat', source_ref VARCHAR(128) DEFAULT '', observed_text TEXT DEFAULT '', confidence DOUBLE PRECISION DEFAULT 0, metadata JSONB DEFAULT '{}', observed_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_memory_observations_memory ON memory_observations (memory_id, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memory_observations_user ON memory_observations (user_id, observed_at DESC)",
    "CREATE TABLE IF NOT EXISTS sessions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), title VARCHAR(200) DEFAULT '新对话', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
    "CREATE TABLE IF NOT EXISTS messages (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), session_id UUID NOT NULL REFERENCES sessions(id), role VARCHAR(16) NOT NULL, content TEXT NOT NULL, msg_type VARCHAR(32) DEFAULT 'text', metadata_ TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title_auto_set BOOLEAN DEFAULT FALSE",
    "CREATE TABLE IF NOT EXISTS session_summaries (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, summary TEXT DEFAULT '', topics JSONB DEFAULT '{}', signals JSONB DEFAULT '{}', message_count INTEGER DEFAULT 0, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_session_summaries_session_id UNIQUE (session_id))",
    "CREATE INDEX IF NOT EXISTS idx_session_summaries_user ON session_summaries (user_id, ended_at DESC)",
    "CREATE TABLE IF NOT EXISTS tacit_profiles (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), summary TEXT DEFAULT '', profile JSONB DEFAULT '{}', version_no INTEGER DEFAULT 1, confidence DOUBLE PRECISION DEFAULT 0, horizon_start TIMESTAMPTZ, horizon_end TIMESTAMPTZ, last_analyzed_at TIMESTAMPTZ, next_review_at TIMESTAMPTZ, status VARCHAR(16) DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_tacit_profiles_user_id UNIQUE (user_id))",
    "CREATE INDEX IF NOT EXISTS idx_tacit_profiles_review ON tacit_profiles (next_review_at) WHERE status = 'active' AND next_review_at IS NOT NULL",
    "CREATE TABLE IF NOT EXISTS tacit_profile_versions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), profile_id UUID NOT NULL REFERENCES tacit_profiles(id) ON DELETE CASCADE, user_id UUID NOT NULL REFERENCES users(id), version_no INTEGER NOT NULL, input_window_start TIMESTAMPTZ, input_window_end TIMESTAMPTZ, base_profile JSONB DEFAULT '{}', new_evidence JSONB DEFAULT '{}', delta JSONB DEFAULT '{}', merged_profile JSONB DEFAULT '{}', decay_applied JSONB DEFAULT '{}', model_version VARCHAR(64) DEFAULT 'rules-v1', prompt_version VARCHAR(64) DEFAULT 'tacit-profile-v1', created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_tacit_profile_versions_user ON tacit_profile_versions (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_tacit_profile_versions_profile ON tacit_profile_versions (profile_id, version_no DESC)",

    "CREATE TABLE IF NOT EXISTS user_soul_inventory (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, template_id UUID NOT NULL REFERENCES soul_templates(id), source VARCHAR(32) NOT NULL DEFAULT 'draw', status VARCHAR(16) NOT NULL DEFAULT 'owned', acquired_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE (user_id, template_id))",
    "CREATE INDEX IF NOT EXISTS idx_user_soul_inventory_user_id ON user_soul_inventory(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_soul_inventory_template_id ON user_soul_inventory(template_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_souls_one_active_per_user ON user_souls(user_id) WHERE status = 'active'",

    "ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
    "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS score INTEGER",
    "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS max_score INTEGER",
    "ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS report_version INTEGER DEFAULT 0",
    "ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS report_generated_at TIMESTAMPTZ",
    "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS answer_version INTEGER DEFAULT 0",
    "ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS interview_type VARCHAR(32) DEFAULT 'comprehensive'",
    "ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS difficulty VARCHAR(16) DEFAULT 'medium'",
    "ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS dimension_scores JSONB",

    "CREATE TABLE IF NOT EXISTS finance_records (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), type VARCHAR(8) NOT NULL, category VARCHAR(32) NOT NULL, amount BIGINT NOT NULL, note TEXT, record_date DATE NOT NULL, source VARCHAR(16) DEFAULT 'manual', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_finance_records_user_date ON finance_records(user_id, record_date)",
    "CREATE TABLE IF NOT EXISTS finance_messages (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), role VARCHAR(16) NOT NULL, content TEXT NOT NULL, record_id UUID REFERENCES finance_records(id), created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_finance_messages_user ON finance_messages(user_id)",

    "CREATE TABLE IF NOT EXISTS travel_plans (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), title VARCHAR(255) DEFAULT '', destination VARCHAR(255) NOT NULL, start_date DATE NOT NULL, days INTEGER NOT NULL, budget INTEGER DEFAULT 0, adults INTEGER DEFAULT 1, children INTEGER DEFAULT 0, preferences JSONB DEFAULT '[]', note TEXT DEFAULT '', saved BOOLEAN DEFAULT FALSE, budget_detail JSONB, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_travel_plans_user ON travel_plans(user_id)",
    "CREATE TABLE IF NOT EXISTS travel_days (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), plan_id UUID NOT NULL REFERENCES travel_plans(id) ON DELETE CASCADE, day_number INTEGER NOT NULL, date DATE NOT NULL, segments JSONB DEFAULT '[]', total_cost INTEGER DEFAULT 0)",
    "CREATE INDEX IF NOT EXISTS idx_travel_days_plan ON travel_days(plan_id)",
]

LOCK_ID = 20240724  # 迁移锁 ID（唯一整数）


async def run_migrations():
    """应用启动时自动执行数据库迁移（10秒超时），多实例互斥"""
    try:
        async with engine.begin() as conn:
            # 尝试获取 advisory lock（非阻塞）
            result = await conn.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": LOCK_ID})
            acquired = result.scalar()
            if not acquired:
                print("[migrate] 迁移锁被其他实例占用，跳过迁移")
                return

            try:
                await conn.execute(text("SET statement_timeout = '10s'"))
                for stmt in MIGRATION_SQL:
                    try:
                        await conn.execute(text(stmt))
                        print(f"[migrate] OK: {stmt[:60]}")
                    except Exception as e:
                        print(f"[migrate] SKIP ({e}): {stmt[:60]}")
                print("[migrate] 数据库迁移完成")
            finally:
                await conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": LOCK_ID})
                print("[migrate] 迁移锁已释放")
    except Exception as e:
        print(f"[migrate] 迁移失败（可忽略）: {e}")
