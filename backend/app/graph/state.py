from dataclasses import dataclass, field


@dataclass
class ChatState:
    user_id: str
    message: str
    conversation_id: str | None = None

    # 运行时填充
    compiled_soul: str = ""
    soul_id: str = ""
    memories: list[dict] = field(default_factory=list)
    tacit_context: str = ""
    query_topics: list[str] = field(default_factory=list)
    session_context: str = ""
    memory_candidates: list[dict] = field(default_factory=list)
    pending_anchors: list[dict] = field(default_factory=list)
    intent: str = "daily"  # daily / interview / complex
    reply: str = ""
    actions: list[dict] = field(default_factory=list)
    error: str | None = None
