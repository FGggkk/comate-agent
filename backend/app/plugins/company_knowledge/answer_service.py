"""基于已检索资料生成带来源的公司知识回答。"""

from collections.abc import AsyncIterator

from app.plugins.company_knowledge.prompts import COMPANY_KNOWLEDGE_SYSTEM_PROMPT, build_answer_prompt
from app.plugins.company_knowledge.retriever import RetrievedChunk
from app.services.model_gateway import gateway


NO_EVIDENCE_REPLY = "当前已发布制度中未找到可引用依据。"


def _build_company_knowledge_answer_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    return build_answer_prompt(
        question,
        [
            {
                "title": chunk.title,
                "version": chunk.version,
                "effective_at": chunk.effective_at or "未标注",
                "section_path": chunk.section_path,
                "content": chunk.content,
            }
            for chunk in chunks
        ],
    )


async def generate_company_knowledge_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """使用和用户端相同的资料提示词生成非流式回答，供验证流程复用。"""
    if not chunks:
        return NO_EVIDENCE_REPLY
    return (await gateway.chat(_build_company_knowledge_answer_prompt(question, chunks), system=COMPANY_KNOWLEDGE_SYSTEM_PROMPT)).strip()


async def stream_company_knowledge_answer(
    question: str,
    chunks: list[RetrievedChunk],
) -> AsyncIterator[str]:
    if not chunks:
        yield NO_EVIDENCE_REPLY
        return
    prompt = _build_company_knowledge_answer_prompt(question, chunks)
    async for text in gateway.stream(prompt, system=COMPANY_KNOWLEDGE_SYSTEM_PROMPT):
        yield text
