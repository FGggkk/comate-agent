"""公司知识的权限过滤与混合检索（BM25 关键词 + pgvector 向量 + RRF 融合）。"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugins.company_knowledge.keyword_retriever import BM25Index, rrf_merge
from app.plugins.company_knowledge.registry import is_query_enabled
from app.services.embedding_service import get_embedding


DEFAULT_TOP_K = 6
MIN_SIMILARITY = 0.35
# User questions may use evidence just below the stricter validation threshold.
MIN_USER_QUERY_SIMILARITY = 0.34
# 混合检索的候选池宽度：向量与 BM25 各自召回的数量，随后 RRF 融合取最终 top_k。
CANDIDATE_TOP_K = 20


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

    now = datetime.now(timezone.utc)
    candidates = await _load_published_candidates(db, knowledge_type, now)
    vector_ranked, vector_similarity = await _vector_rank(
        db,
        question,
        top_k=CANDIDATE_TOP_K,
        where_clause=PUBLISHED_WHERE,
        params={"knowledge_type": knowledge_type, "now": now},
    )
    keyword_ranked = _keyword_rank(question, candidates)
    fused_ids = rrf_merge(vector_ranked, keyword_ranked, limit=top_k)

    chunks = []
    for chunk_id in fused_ids:
        candidate = candidates.get(chunk_id)
        if not candidate:
            continue
        similarity = vector_similarity.get(chunk_id, 0.0)
        # 向量侧召回的过低相似度分片剔除；仅由关键词召回（不在向量 Top-K 内）的分片豁免阈值。
        if similarity < MIN_USER_QUERY_SIMILARITY and chunk_id in vector_similarity:
            continue
        chunks.append(_to_retrieved_chunk(candidate, similarity))
    return chunks


async def preview_company_knowledge_chunk_set(
    question: str,
    db: AsyncSession,
    *,
    source_id: str,
    chunk_set_id: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """管理员发布前验证指定分片集（混合检索），不要求资料已发布。"""
    candidates = await _load_chunk_set_candidates(db, source_id, chunk_set_id)
    vector_ranked, vector_similarity = await _vector_rank(
        db,
        question,
        top_k=CANDIDATE_TOP_K,
        where_clause=CHUNK_SET_WHERE,
        params={"source_id": source_id, "chunk_set_id": chunk_set_id},
    )
    keyword_ranked = _keyword_rank(question, candidates)
    fused_ids = rrf_merge(vector_ranked, keyword_ranked, limit=top_k)

    chunks = []
    for chunk_id in fused_ids:
        candidate = candidates.get(chunk_id)
        if not candidate:
            continue
        similarity = vector_similarity.get(chunk_id, 0.0)
        chunks.append(_to_retrieved_chunk(candidate, similarity))
    return chunks


# 用户端：已发布且生效、属于 active chunk_set 的分片（向量与 BM25 共用的过滤条件）
PUBLISHED_WHERE = (
    "source.knowledge_type = :knowledge_type"
    " AND source.status = 'published'"
    " AND source.access_scope = 'all_users'"
    " AND source.effective_at <= :now"
    " AND (source.expires_at IS NULL OR source.expires_at > :now)"
    " AND source.active_chunk_set_id = chunk_set.id"
    " AND chunk_set.status IN ('indexed', 'validated', 'published')"
    " AND chunk.status = 'indexed'"
    " AND chunk.embedding IS NOT NULL"
)

# 管理端：指定资料的分片版本（验证预览用）
CHUNK_SET_WHERE = (
    "source.id = CAST(:source_id AS uuid)"
    " AND chunk_set.id = CAST(:chunk_set_id AS uuid)"
    " AND chunk_set.status IN ('indexed', 'validated')"
    " AND chunk.status = 'indexed'"
    " AND chunk.embedding IS NOT NULL"
)


async def _load_published_candidates(
    db: AsyncSession,
    knowledge_type: str,
    now: datetime,
) -> dict[str, dict]:
    """加载已发布且生效、属于 active chunk_set 的全部分片，供 BM25 索引构建。"""
    result = await db.execute(
        text(
            f"""
            SELECT
                chunk.id AS chunk_id,
                chunk_set.id AS chunk_set_id,
                source.id AS source_id,
                source.title,
                source.version,
                source.effective_at,
                chunk.section_path,
                chunk.content
            FROM company_knowledge_chunks AS chunk
            JOIN company_knowledge_sources AS source ON source.id = chunk.source_id
            JOIN company_knowledge_chunk_sets AS chunk_set ON chunk_set.id = chunk.chunk_set_id
            WHERE {PUBLISHED_WHERE}
            """
        ),
        {"knowledge_type": knowledge_type, "now": now},
    )
    candidates: dict[str, dict] = {}
    for row in result.mappings().all():
        candidates[str(row["chunk_id"])] = _candidate_from_row(row)
    return candidates


async def _load_chunk_set_candidates(
    db: AsyncSession,
    source_id: str,
    chunk_set_id: str,
) -> dict[str, dict]:
    result = await db.execute(
        text(
            f"""
            SELECT
                chunk.id AS chunk_id,
                chunk_set.id AS chunk_set_id,
                source.id AS source_id,
                source.title,
                source.version,
                source.effective_at,
                chunk.section_path,
                chunk.content
            FROM company_knowledge_chunks AS chunk
            JOIN company_knowledge_sources AS source ON source.id = chunk.source_id
            JOIN company_knowledge_chunk_sets AS chunk_set ON chunk_set.id = chunk.chunk_set_id
            WHERE {CHUNK_SET_WHERE}
            """
        ),
        {"source_id": source_id, "chunk_set_id": chunk_set_id},
    )
    candidates: dict[str, dict] = {}
    for row in result.mappings().all():
        candidates[str(row["chunk_id"])] = _candidate_from_row(row)
    return candidates


def _candidate_from_row(row) -> dict:
    effective_at = row["effective_at"]
    return {
        "chunk_id": str(row["chunk_id"]),
        "chunk_set_id": str(row["chunk_set_id"]),
        "source_id": str(row["source_id"]),
        "title": row["title"],
        "version": row["version"],
        "effective_at": effective_at.date().isoformat() if effective_at else None,
        "section_path": row["section_path"] or "",
        "content": row["content"],
    }


def _keyword_rank(question: str, candidates: dict[str, dict]) -> list[str]:
    if not candidates:
        return []
    index = BM25Index([(chunk_id, candidate["content"]) for chunk_id, candidate in candidates.items()])
    return [hit.chunk_id for hit in index.search(question, top_k=CANDIDATE_TOP_K)]


async def _vector_rank(
    db: AsyncSession,
    question: str,
    *,
    top_k: int,
    where_clause: str,
    params: dict,
) -> tuple[list[str], dict[str, float]]:
    """向量召回 Top-K，返回 (按相似度降序的 chunk_id 列表, chunk_id -> similarity)。

    where_clause 必须与对应候选加载的过滤条件完全一致，保证向量与 BM25 候选池相同。
    """
    vector = await get_embedding(question)
    if not vector:
        raise RetrievalError("暂时无法生成查询向量")
    vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
    query_params = dict(params)
    query_params.update({"query_vector": vector_literal, "top_k": top_k})
    result = await db.execute(
        text(
            f"""
            SELECT
                chunk.id AS chunk_id,
                1 - (chunk.embedding <=> CAST(:query_vector AS vector)) AS similarity
            FROM company_knowledge_chunks AS chunk
            JOIN company_knowledge_sources AS source ON source.id = chunk.source_id
            JOIN company_knowledge_chunk_sets AS chunk_set ON chunk_set.id = chunk.chunk_set_id
            WHERE {where_clause}
            ORDER BY chunk.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        ),
        query_params,
    )
    ranked: list[str] = []
    similarity_map: dict[str, float] = {}
    for row in result.mappings().all():
        chunk_id = str(row["chunk_id"])
        similarity = float(row["similarity"] or 0)
        ranked.append(chunk_id)
        similarity_map[chunk_id] = similarity
    return ranked, similarity_map


def _to_retrieved_chunk(candidate: dict, similarity: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=candidate["chunk_id"],
        chunk_set_id=candidate["chunk_set_id"],
        source_id=candidate["source_id"],
        title=candidate["title"],
        version=candidate["version"],
        effective_at=candidate["effective_at"],
        section_path=candidate["section_path"],
        content=candidate["content"],
        similarity=similarity,
    )
