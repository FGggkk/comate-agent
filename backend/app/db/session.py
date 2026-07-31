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
    "CREATE TABLE IF NOT EXISTS memory_documents (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), doc_type VARCHAR(16) NOT NULL, content TEXT DEFAULT '', version_no INTEGER DEFAULT 1, char_limit INTEGER DEFAULT 0, item_limit INTEGER DEFAULT 0, source_hash VARCHAR(64) DEFAULT '', file_path VARCHAR(1024) DEFAULT '', file_hash VARCHAR(64) DEFAULT '', status VARCHAR(16) DEFAULT 'active', sync_status VARCHAR(16) DEFAULT 'synced', edited_by VARCHAR(16) DEFAULT 'app', metadata JSONB DEFAULT '{}', generated_at TIMESTAMPTZ DEFAULT NOW(), last_imported_at TIMESTAMPTZ, last_exported_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, next_review_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
    "ALTER TABLE memory_documents ADD COLUMN IF NOT EXISTS file_path VARCHAR(1024) DEFAULT ''",
    "ALTER TABLE memory_documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64) DEFAULT ''",
    "ALTER TABLE memory_documents ADD COLUMN IF NOT EXISTS sync_status VARCHAR(16) DEFAULT 'synced'",
    "ALTER TABLE memory_documents ADD COLUMN IF NOT EXISTS edited_by VARCHAR(16) DEFAULT 'app'",
    "ALTER TABLE memory_documents ADD COLUMN IF NOT EXISTS last_imported_at TIMESTAMPTZ",
    "ALTER TABLE memory_documents ADD COLUMN IF NOT EXISTS last_exported_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_memory_documents_user_type_status ON memory_documents (user_id, doc_type, status)",
    "CREATE INDEX IF NOT EXISTS idx_memory_documents_sync ON memory_documents (user_id, doc_type, sync_status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_documents_active ON memory_documents (user_id, doc_type) WHERE status = 'active'",
    "CREATE INDEX IF NOT EXISTS idx_memory_documents_review ON memory_documents (next_review_at) WHERE status = 'active' AND next_review_at IS NOT NULL",

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
    # 购物计划
    "CREATE TABLE IF NOT EXISTS shopping_plans (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), demand TEXT NOT NULL, plans JSONB NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_shopping_plans_user ON shopping_plans(user_id)",
    "ALTER TABLE shopping_plans ADD COLUMN IF NOT EXISTS favorited VARCHAR(16) DEFAULT 'false'",

    # ===== 管理端 & 计费体系 =====
    "CREATE TABLE IF NOT EXISTS admins (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, nickname VARCHAR(64), role VARCHAR(16) DEFAULT 'admin', status VARCHAR(16) DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT NOW(), last_login TIMESTAMPTZ)",
    "CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email)",
    "CREATE TABLE IF NOT EXISTS redemption_codes (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), code VARCHAR(32) UNIQUE NOT NULL, amount INTEGER NOT NULL, batch_no VARCHAR(64), max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0, expires_at TIMESTAMPTZ, status VARCHAR(16) DEFAULT 'active', note TEXT, created_by UUID REFERENCES admins(id), created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_redemption_codes_code ON redemption_codes(code)",
    "CREATE INDEX IF NOT EXISTS idx_redemption_codes_status ON redemption_codes(status)",
    "CREATE TABLE IF NOT EXISTS redemption_usage (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), code_id UUID NOT NULL REFERENCES redemption_codes(id), user_id UUID NOT NULL REFERENCES users(id), amount INTEGER NOT NULL, redeemed_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_redemption_usage_user ON redemption_usage(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_redemption_usage_code ON redemption_usage(code_id)",
    "CREATE TABLE IF NOT EXISTS balance_accounts (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id) UNIQUE, balance INTEGER DEFAULT 0, total_recharged INTEGER DEFAULT 0, total_consumed INTEGER DEFAULT 0, updated_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_balance_accounts_user ON balance_accounts(user_id)",
    "CREATE TABLE IF NOT EXISTS balance_transactions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), change INTEGER NOT NULL, balance_after INTEGER NOT NULL, type VARCHAR(16) NOT NULL, ref_type VARCHAR(32), ref_id VARCHAR(64), note TEXT, created_at TIMESTAMPTZ DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_balance_transactions_user ON balance_transactions(user_id, created_at DESC)",
    "CREATE TABLE IF NOT EXISTS billing_rules (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), item_key VARCHAR(64) UNIQUE NOT NULL, item_name VARCHAR(64) NOT NULL, price INTEGER DEFAULT 0, enabled BOOLEAN DEFAULT TRUE, updated_at TIMESTAMPTZ DEFAULT NOW())",
    "INSERT INTO billing_rules (item_key, item_name, price, enabled) VALUES ('chat_round', '日常对话', 1, TRUE), ('interview_question', '面试提问', 2, TRUE), ('interview_report', '面试报告', 5, TRUE), ('shopping_plan', '购物计划', 10, TRUE), ('travel_plan', '旅游规划', 8, TRUE), ('finance_parse', '记账AI解析', 1, TRUE), ('reroll_hint', '重出题/思路提示', 2, TRUE) ON CONFLICT (item_key) DO NOTHING",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_redemption_usage_code_user ON redemption_usage(code_id, user_id)",
    "UPDATE redemption_codes SET status = 'used' WHERE status = 'active' AND used_count >= max_uses",
    "UPDATE redemption_codes SET status = 'expired' WHERE status IN ('active', 'used') AND expires_at IS NOT NULL AND expires_at < NOW()",
    "CREATE TABLE IF NOT EXISTS app_settings (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), key VARCHAR(64) UNIQUE NOT NULL, value TEXT DEFAULT '', updated_at TIMESTAMPTZ DEFAULT NOW())",
    "INSERT INTO app_settings (key, value) VALUES ('register_bonus', '20'), ('billing_enforce', 'false') ON CONFLICT (key) DO NOTHING",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'active'",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS color VARCHAR(16)",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'builtin'",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES admins(id)",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS card_image VARCHAR(512)",
    "ALTER TABLE soul_templates ADD COLUMN IF NOT EXISTS avatar_image VARCHAR(512)",
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
