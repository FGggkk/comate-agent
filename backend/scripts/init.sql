-- 伴行agent — 数据库初始化脚本
-- 用于服务器首次建表

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    onboarding_status VARCHAR(32) DEFAULT 'none',
    created_at TIMESTAMPTZ DEFAULT now(),
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS soul_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    dimensions JSONB DEFAULT '{}',
    soul_markdown TEXT NOT NULL,
    version VARCHAR(32) DEFAULT '1.0.0',
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_souls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    template_id UUID REFERENCES soul_templates(id),
    version_no INTEGER DEFAULT 1,
    soul_markdown TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    layer VARCHAR(16) NOT NULL,
    memory_type VARCHAR(32) DEFAULT 'general',
    summary VARCHAR(500) NOT NULL,
    content JSONB DEFAULT '{}',
    source_type VARCHAR(32) DEFAULT 'user_input',
    sensitivity VARCHAR(16) DEFAULT 'normal',
    user_confirmed BOOLEAN DEFAULT FALSE,
    is_inference BOOLEAN DEFAULT FALSE,
    status VARCHAR(16) DEFAULT 'active',
    event_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    confidence DOUBLE PRECISION DEFAULT 0,
    observed_count INTEGER DEFAULT 0,
    last_observed_at TIMESTAMPTZ,
    dedupe_key VARCHAR(160),
    review_after TIMESTAMPTZ,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_embedding_hnsw
ON memory_items USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memory_items_expiry
ON memory_items (user_id, expires_at)
WHERE status = 'active' AND expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_items_review
ON memory_items (user_id, review_after)
WHERE status = 'active' AND review_after IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_items_dedupe
ON memory_items (user_id, layer, memory_type, dedupe_key)
WHERE status = 'active' AND dedupe_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS memory_observations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    source_type VARCHAR(32) DEFAULT 'chat',
    source_ref VARCHAR(128) DEFAULT '',
    observed_text TEXT DEFAULT '',
    confidence DOUBLE PRECISION DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    observed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_observations_memory
ON memory_observations (memory_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_observations_user
ON memory_observations (user_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS forbidden_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    topic_summary VARCHAR(500) NOT NULL,
    original_phrase TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pending_anchors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    topic_summary VARCHAR(500) NOT NULL,
    context TEXT DEFAULT '',
    status VARCHAR(16) DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verification_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL,
    code VARCHAR(6) NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    resume_text TEXT DEFAULT '',
    target_role VARCHAR(255) DEFAULT '',
    target_company VARCHAR(255) DEFAULT '',
    status VARCHAR(16) DEFAULT 'in_progress',
    round_number INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS interview_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES interview_sessions(id),
    round_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    user_answer TEXT,
    evaluation TEXT,
    status VARCHAR(16) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    content VARCHAR(500) NOT NULL,
    remind_at TIMESTAMPTZ NOT NULL,
    triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);
