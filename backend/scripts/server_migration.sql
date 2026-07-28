-- 已有数据库迁移 pgvector
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

-- 用户表新增字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);
