"""公司知识问答的来源约束提示词。"""


COMPANY_KNOWLEDGE_SYSTEM_PROMPT = """你是伴行的公司知识问答助手。
你只能依据本次提供的公司资料片段作答，不能把模型常识、个人记忆或猜测说成公司制度。
资料不足、存在冲突或无法支持结论时，直接说明“当前已发布制度中未找到可引用依据”。
每个结论都必须由至少一段资料支持；回答简洁、准确，必要时说明适用条件；不要在正文中编造来源编号。
"""


def build_answer_prompt(question: str, chunks: list[dict]) -> str:
    sources = []
    for index, chunk in enumerate(chunks, start=1):
        sources.append(
            "\n".join(
                [
                    f"[资料 {index}] {chunk['title']}（版本 {chunk['version']}，生效 {chunk['effective_at']}）",
                    f"章节：{chunk['section_path'] or '未标注章节'}",
                    f"内容：{chunk['content']}",
                ]
            )
        )
    return f"""用户问题：{question}

可引用资料：
{chr(10).join(sources)}

请基于可引用资料回答用户问题。"""
