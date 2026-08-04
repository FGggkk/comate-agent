"""公司知识的权限过滤与 pgvector 召回。"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugins.company_knowledge.registry import is_query_enabled
from app.services.embedding_service import get_embedding


DEFAULT_TOP_K = 6
MIN_SIMILARITY = 0.35


class RetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_id: str
    title: str
    version: str
    effective_at: str | None
    section_path: str
    content: str
    similarity: float
    chunk_set_id: str | None = None

    def to_citation(self) -> dict:
        return {
            "source_id": self.source_id,
            "chunk_id": self.chunk_id,
            "chunk_set_id": self.chunk_set_id,
            "title": self.title,
            "version": self.version,
            "effective_at": self.effective_at,
            "section_path": self.section_path,
            "excerpt": self.content[:240],
            "similarity": round(self.similarity, 4),
        }

    def to_preview(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "chunk_set_id": self.chunk_set_id,
            "section_path": self.section_path,
            "content": self.content,
            "similarity": round(self.similarity, 4),
            "meets_minimum_similarity": self.similarity >= MIN_SIMILARITY,
        }


async def retrieve_company_knowledge(
    question: str,
    knowledge_type: str,
    db: AsyncSession,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    if not is_query_enabled(knowledge_type):
        raise RetrievalError("该资料类型暂未启用查询")

    vector = await get_embedding(question)
    if not vector:
        raise RetrievalError("暂时无法生成查询向量")
    vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
    now = datetime.now(timezone.utc)
    result = await db.execute(
        text(
            """
            SELECT
                chunk.id AS chunk_id,
                chunk_set.id AS chunk_set_id,
                source.id AS source_id,
                source.title,
                source.version,
                source.effective_at,
                chunk.section_path,
                chunk.content,
                1 - (chunk.embedding <=> CAST(:query_vector AS vector)) AS similarity
            FROM company_knowledge_chunks AS chunk
            JOIN company_knowledge_sources AS source ON source.id = chunk.source_id
            JOIN company_knowledge_chunk_sets AS chunk_set ON chunk_set.id = chunk.chunk_set_id
            WHERE source.knowledge_type = :knowledge_type
              AND source.status = 'published'
              AND source.access_scope = 'all_users'
              AND source.effective_at <= :now
              AND (source.expires_at IS NULL OR source.expires_at > :now)
              AND source.active_chunk_set_id = chunk_set.id
              AND chunk_set.status IN ('indexed', 'validated')
              AND chunk.status = 'indexed'
              AND chunk.embedding IS NOT NULL
            ORDER BY chunk.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        ),
        {"query_vector": vector_literal, "knowledge_type": knowledge_type, "now": now, "top_k": top_k},
    )
    chunks = []
    for row in result.mappings().all():
        similarity = float(row["similarity"] or 0)
        if similarity < MIN_SIMILARITY:
            continue
        effective_at = row["effective_at"]
        chunks.append(
            RetrievedChunk(
                chunk_id=str(row["chunk_id"]),
                chunk_set_id=str(row["chunk_set_id"]),
                source_id=str(row["source_id"]),
                title=row["title"],
                version=row["version"],
                effective_at=effective_at.date().isoformat() if effective_at else None,
                section_path=row["section_path"] or "",
                content=row["content"],
                similarity=similarity,
            )
        )
    return chunks


async def preview_company_knowledge_chunk_set(
    question: str,
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """管理员发布前验证指定分片集，不要求资料已发布。"""
    vector = await get_embedding(question)
    if not vector:
        raise RetrievalError("暂时无法生成查询向量")
    vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
    result = await db.execute(
        text(
            """
            SELECT
                chunk.id AS chunk_id,
                chunk_set.id AS chunk_set_id,
                source.id AS source_id,
                source.title,
                source.version,
                source.effective_at,
                chunk.section_path,
                chunk.content,
                1 - (chunk.embedding <=> CAST(:query_vector AS vector)) AS similarity
            FROM company_knowledge_chunks AS chunk
            JOIN company_knowledge_sources AS source ON source.id = chunk.source_id
            JOIN company_knowledge_chunk_sets AS chunk_set ON chunk_set.id = chunk.chunk_set_id
            WHERE source.id = CAST(:source_id AS uuid)
              AND chunk_set.id = CAST(:chunk_set_id AS uuid)
              AND chunk_set.status IN ('indexed', 'validated')
              AND chunk.status = 'indexed'
              AND chunk.embedding IS NOT NULL
            ORDER BY chunk.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        ),
        {
            "query_vector": vector_literal,
            "source_id": source_id,
            "chunk_set_id": chunk_set_id,
            "top_k": top_k,
        },
    )
    chunks = []
    for row in result.mappings().all():
        effective_at = row["effective_at"]
        chunks.append(
            RetrievedChunk(
                chunk_id=str(row["chunk_id"]),
                chunk_set_id=str(row["chunk_set_id"]),
                source_id=str(row["source_id"]),
                title=row["title"],
                version=row["version"],
                effective_at=effective_at.date().isoformat() if effective_at else None,
                section_path=row["section_path"] or "",
                content=row["content"],
                similarity=float(row["similarity"] or 0),
            )
        )
    return chunks
