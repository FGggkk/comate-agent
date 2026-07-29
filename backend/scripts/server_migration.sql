-- 已有数据库迁移 pgvector
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding vector(1536);
CREATE INDEX IF NOT EXISTS idx_memory_embedding_hnsw
ON memory_items USING hnsw (embedding vector_cosine_ops);

-- 记忆结构化字段
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS event_at TIMESTAMPTZ;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION DEFAULT 0;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS observed_count INTEGER DEFAULT 0;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS last_observed_at TIMESTAMPTZ;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(160);
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS review_after TIMESTAMPTZ;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS scope VARCHAR(16) DEFAULT 'global';
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS topic_tags JSONB DEFAULT '[]';

UPDATE memory_items
SET event_at = (content->>'event_at')::timestamptz
WHERE event_at IS NULL
  AND content ? 'event_at'
  AND content->>'event_at' ~ '^\d{4}-\d{2}-\d{2}';

UPDATE memory_items
SET expires_at = (content->>'expires_at')::timestamptz
WHERE expires_at IS NULL
  AND content ? 'expires_at'
  AND content->>'expires_at' ~ '^\d{4}-\d{2}-\d{2}';

UPDATE memory_items
SET scope = content->>'scope'
WHERE content ? 'scope'
  AND content->>'scope' IN ('global', 'topic', 'session', 'ephemeral');

UPDATE memory_items
SET topic_tags = content->'topic_tags'
WHERE content ? 'topic_tags'
  AND jsonb_typeof(content->'topic_tags') = 'array';

CREATE INDEX IF NOT EXISTS idx_memory_items_expiry
ON memory_items (user_id, expires_at)
WHERE status = 'active' AND expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_items_review
ON memory_items (user_id, review_after)
WHERE status = 'active' AND review_after IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_items_dedupe
ON memory_items (user_id, layer, memory_type, dedupe_key)
WHERE status = 'active' AND dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_items_scope
ON memory_items (user_id, layer, scope)
WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_memory_items_topic_tags
ON memory_items USING GIN (topic_tags);

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

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(200) DEFAULT '新对话',
    title_auto_set BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    msg_type VARCHAR(32) DEFAULT 'text',
    metadata_ TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title_auto_set BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS session_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    summary TEXT DEFAULT '',
    topics JSONB DEFAULT '{}',
    signals JSONB DEFAULT '{}',
    message_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_session_summaries_session_id UNIQUE (session_id)
);

CREATE INDEX IF NOT EXISTS idx_session_summaries_user
ON session_summaries (user_id, ended_at DESC);

CREATE TABLE IF NOT EXISTS tacit_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    summary TEXT DEFAULT '',
    profile JSONB DEFAULT '{}',
    version_no INTEGER DEFAULT 1,
    confidence DOUBLE PRECISION DEFAULT 0,
    horizon_start TIMESTAMPTZ,
    horizon_end TIMESTAMPTZ,
    last_analyzed_at TIMESTAMPTZ,
    next_review_at TIMESTAMPTZ,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_tacit_profiles_user_id UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_tacit_profiles_review
ON tacit_profiles (next_review_at)
WHERE status = 'active' AND next_review_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS tacit_profile_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES tacit_profiles(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    version_no INTEGER NOT NULL,
    input_window_start TIMESTAMPTZ,
    input_window_end TIMESTAMPTZ,
    base_profile JSONB DEFAULT '{}',
    new_evidence JSONB DEFAULT '{}',
    delta JSONB DEFAULT '{}',
    merged_profile JSONB DEFAULT '{}',
    decay_applied JSONB DEFAULT '{}',
    model_version VARCHAR(64) DEFAULT 'rules-v1',
    prompt_version VARCHAR(64) DEFAULT 'tacit-profile-v1',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tacit_profile_versions_user
ON tacit_profile_versions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tacit_profile_versions_profile
ON tacit_profile_versions (profile_id, version_no DESC);

-- 用户表新增字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);
