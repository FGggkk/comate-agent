"""公司知识问答的来源约束提示词。"""


COMPANY_KNOWLEDGE_SYSTEM_PROMPT = """你是伴行的公司知识问答助手。
你只能依据本次提供的公司资料片段作答，不能把模型常识、个人记忆或猜测说成公司制度。
资料不足、存在冲突或无法支持结论时，直接说明“当前已发布制度中未找到可引用依据”。
每个结论都必须由至少一段资料支持；回答简洁、准确，必要时说明适用条件；不要在正文中编造来源编号。
回答涉及具体规则或条款时，必须点名所依据的制度名称（如“按《员工考勤与休假管理制度》”），不要使用“根据相关资料”“根据相关制度”这类笼统表述；多条制度共同支撑时，分别点名各制度名称。
"""


def build_answer_prompt(question: str, chunks: list[dict]) -> str:
    sources = []
    for index, chunk in enumerate(chunks, start=1):
        lines = [
            f"[资料 {index}] {chunk['title']}（版本 {chunk['version']}，生效 {chunk['effective_at']}）",
            f"章节：{chunk['section_path'] or '未标注章节'}",
        ]
        context = chunk.get("contextual_description") or ""
        if context:
            lines.append(f"上下文：{context}")
        lines.append(f"内容：{chunk['content']}")
        sources.append("\n".join(lines))
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


CHUNK_REFINE_SYSTEM_PROMPT = """你是公司知识库的文档切分顾问，负责对"自动切分"产生的分片做语义边界裁决。
目标：让分片成为语义完整、主题集中的片段。
规则：
- 只判断分片之间的合并或拆分，绝不重写、修改任何正文内容。
- merge_with_next：当前分片与下一分片语义连续（同一主题、同一流程、同一条款），且合并后仍接近目标块长度时使用。
- split：当前分片包含多个不相关主题时拆开；必须给出 split_at（在分片正文中的字符偏移，应落在句子边界附近）。
- keep：无需调整。
- 每个分片必须且只能给出一个决策，不要遗漏。
仅返回 JSON 数组，格式为 [{"chunk_index": 0, "action": "keep|merge_with_next|split", "split_at": null, "reason": "简短原因"}]，不要输出 Markdown 或其他文字。"""


def build_chunk_refine_prompt(source_title: str, chunks: list[dict], target_len: int) -> str:
    """构造 LLM 边界裁决的输入：每块只送章节路径与首/尾片段，控制 token 成本。"""
    lines = [f"资料标题：{source_title}", f"目标块长度：{target_len} 字符", "", "候选分片："]
    for item in chunks:
        lines.append(
            "\n".join(
                [
                    f"[分片 {item['index']}] 章节：{item['section_path'] or '未标注'}，字数：{item['char_count']}",
                    f"开头：{item['head']}",
                    f"结尾：{item['tail']}",
                ]
            )
        )
    return "\n".join(lines)


CONTEXTUALIZE_SYSTEM_PROMPT = """你是公司知识库的文档分片标注助手。
为给定的分片生成 1~2 句"上下文描述"，说明这段内容在讲什么、属于哪份文档的哪个章节，帮助检索与回答时理解分片所处语境。
要求：
- 只做客观概括，不新增、不推测文档未表达的信息。
- 描述要能脱离正文独立理解（例如：这是《员工考勤与休假管理制度》第四章年假部分的条款说明）。
- 直接输出描述文本，不要输出 Markdown 或其他文字。"""


def build_contextualize_prompt(
    source_title: str,
    section_path: str,
    prev_tail: str,
    content: str,
    next_head: str,
) -> str:
    """构造单个分片上下文描述生成的输入：文档标题 + 章节 + 前后块片段 + 本块内容。"""
    return f"""文档标题：{source_title}
章节：{section_path or '未标注'}
上一分片结尾：{prev_tail or '（无）'}
本分片内容：
{content}
下一分片开头：{next_head or '（无）'}

请为本分片生成 1~2 句上下文描述。"""


GRAPH_EXTRACT_SYSTEM_PROMPT = """你是公司知识库的文档关系抽取助手。
从给定制度资料中抽取它与另一份制度文档之间的显式关系。
关系类型（只允许这四种）：
- cite 引用：本文档明确引用了另一份制度/文档（如"按《考勤制度》执行"）。
- supersede 替代：本文档替代了另一份文档（如"自本制度发布之日起，原《XX规定》废止"）。
- parent 上下位：本文档与另一份文档存在总则/细则的上下级关系。
- related 关联：本文档与另一份文档主题紧密关联（如同一流程的上下游）。
规则：
- 只抽取原文显式表达的关系，必须附证据原文片段；不推测、不编造。
- 目标文档尽量使用其完整标题。
仅返回 JSON 数组，格式为 [{"relation_type": "cite", "target_title": "目标文档完整标题", "evidence": "原文证据片段"}]，不要输出 Markdown 或其他文字。"""


def build_graph_extract_prompt(source_title: str, content: str, known_titles: list[str]) -> str:
    """构造关系抽取输入：当前资料（截断）+ 可指向的目标文档标题列表。"""
    titles = "\n".join(f"- {title}" for title in known_titles)
    return f"""当前资料标题：{source_title}
当前资料正文：
{content[:6000]}

已有制度文档标题列表（目标文档只能从列表中选择）：
{titles}

请抽取当前资料与列表中文档的关系。"""
