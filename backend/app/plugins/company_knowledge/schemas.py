"""公司知识库在用户端和管理端共享的请求响应契约。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


KnowledgeTypeKey = Literal[
    "policy",
    "faq",
    "history",
    "news",
    "department_knowledge",
]


class CompanyKnowledgeQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    knowledge_type: KnowledgeTypeKey = "policy"
    input_mode: Literal["text", "voice"] = "text"


class CompanyKnowledgeSourceCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    knowledge_type: KnowledgeTypeKey = "policy"
    category: str = Field(default="", max_length=64)
    effective_at: datetime
    expires_at: datetime | None = None
    access_scope: str = Field(default="all_users", max_length=32)
    metadata: dict = Field(default_factory=dict)


class CompanyKnowledgeSourceResponse(BaseModel):
    id: str
    title: str
    version: str
    knowledge_type: KnowledgeTypeKey
    status: str
    effective_at: datetime | None = None
    expires_at: datetime | None = None


class CompanyKnowledgeTypeResponse(BaseModel):
    key: KnowledgeTypeKey
    label: str
    description: str
    icon: str
    import_enabled: bool
    query_enabled: bool
    user_visible: bool
    required_metadata: list[str]
