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


VALIDATION_EVALUATOR_SYSTEM_PROMPT = """你负责评估公司知识库问答的发布前质量。
只以“预期证据”判断回答是否正确且忠实。
判断规则：
- 回答的结论必须有预期证据支撑；无证据支撑的编造视为不忠实。
- 允许无争议的常识推断（例如由出生日期和当前日期推算年龄、由条款计算天数），只要回答基于证据中的事实、且推断不改变事实本身；这类推断不判为不忠实。你评估时可以使用当前日期等常识做推算。
- 若回答引用了预期证据之外的内容（如检索命中的其他切片），只要该内容与预期证据同源且未偏离，仍视为忠实。
correctness 衡量回答是否正确回答问题；faithfulness 衡量回答中的结论是否有预期证据支持；分数范围均为 0 到 1。
仅返回 JSON 对象，格式为 {"correctness": 0.0, "faithfulness": 0.0, "verdict": "pass 或 fail", "reason": "简短原因"}，不要输出 Markdown 或其他文字。"""


def build_validation_evaluation_prompt(
    question: str,
    answer: str,
    expected_chunks: list[dict],
    retrieved_chunks: list[dict] | None = None,
) -> str:
    evidence = []
    for index, chunk in enumerate(expected_chunks, start=1):
        evidence.append(
            "\n".join(
                [
                    f"[预期证据 {index}] {chunk['title']}（版本 {chunk['version']}）",
                    f"章节：{chunk['section_path'] or '未标注章节'}",
                    f"内容：{chunk['content']}",
                ]
            )
        )
    for index, chunk in enumerate(retrieved_chunks or [], start=1):
        evidence.append(
            "\n".join(
                [
                    f"[检索证据 {index}] {chunk['title']}（版本 {chunk['version']}）",
                    f"章节：{chunk['section_path'] or '未标注章节'}",
                    f"内容：{chunk['content']}",
                ]
            )
        )
    return f"""测试问题：{question}

RAG 回答：{answer}

证据：
{chr(10).join(evidence)}

请评估该回答。"""
