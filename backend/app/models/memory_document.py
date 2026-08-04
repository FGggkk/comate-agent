import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .user import Base


class MemoryDocument(Base):
    """用户可维护的 Markdown 记忆文档。

    USER/MEMORY/BOUNDARY/DELTA 是用户看得见、改得动的实体文档；
    这张表记录它们的版本、内容缓存、文件路径、hash 和同步状态。
    """

    __tablename__ = "memory_documents"
    __table_args__ = (
        Index("idx_memory_documents_user_type_status", "user_id", "doc_type", "status"),
        Index("idx_memory_documents_sync", "user_id", "doc_type", "sync_status"),
        Index(
            "uq_memory_documents_active",
            "user_id",
            "doc_type",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "idx_memory_documents_review",
            "next_review_at",
            postgresql_where=text("status = 'active' AND next_review_at IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    char_limit: Mapped[int] = mapped_column(Integer, default=0)
    item_limit: Mapped[int] = mapped_column(Integer, default=0)
    source_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    file_path: Mapped[str] = mapped_column(String(1024), default="")
    file_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    sync_status: Mapped[str] = mapped_column(String(16), default="synced", index=True)
    edited_by: Mapped[str] = mapped_column(String(16), default="app")
    document_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=func.now())
