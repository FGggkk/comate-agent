-- 已有数据库迁移 pgvector
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding vector(1536);
CREATE INDEX IF NOT EXISTS idx_memory_embedding_hnsw
ON memory_items USING hnsw (embedding vector_cosine_ops);

-- 用户表新增字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);
