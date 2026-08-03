"""公司知识消息与个人画像的边界规则。"""


COMPANY_KNOWLEDGE_MESSAGE_TYPE = "company_knowledge"


def is_company_knowledge_message(message) -> bool:
    return getattr(message, "msg_type", "text") == COMPANY_KNOWLEDGE_MESSAGE_TYPE


def profile_safe_messages(messages):
    """制度问答保留在会话中，但不作为人物画像的原始信号。"""
    return [message for message in messages if not is_company_knowledge_message(message)]
