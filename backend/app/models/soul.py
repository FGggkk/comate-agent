import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .user import Base


class SoulTemplate(Base):
    __tablename__ = "soul_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    dimensions: Mapped[dict] = mapped_column(JSONB, default=dict)
    soul_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    status: Mapped[str] = mapped_column(String(16), default="active")
    # 角色管理扩展字段
    tags: Mapped[list] = mapped_column(JSONB, default=list)  # 角色标签
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 主题色
    card_image: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 卡面图
    avatar_image: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 角色头像图
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序权重（小在前）
    source: Mapped[str] = mapped_column(String(32), default="builtin")  # builtin / custom / imported
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class UserSoul(Base):
    __tablename__ = "user_souls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("soul_templates.id"), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    soul_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserSoulInventory(Base):
    __tablename__ = "user_soul_inventory"
    __table_args__ = (
        UniqueConstraint("user_id", "template_id", name="uq_user_soul_inventory_user_template"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("soul_templates.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="draw", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="owned", nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
