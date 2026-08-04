import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .user import Base


class SessionSummary(Base):
    __tablename__ = "session_summaries"
    __table_args__ = (UniqueConstraint("session_id", name="uq_session_summaries_session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[dict] = mapped_column(JSONB, default=dict)
    signals: Mapped[dict] = mapped_column(JSONB, default=dict)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=func.now())


class TacitProfile(Base):
    __tablename__ = "tacit_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_tacit_profiles_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    horizon_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    horizon_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=func.now())


class TacitProfileVersion(Base):
    __tablename__ = "tacit_profile_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tacit_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    input_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    base_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    new_evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    delta: Mapped[dict] = mapped_column(JSONB, default=dict)
    merged_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    decay_applied: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_version: Mapped[str] = mapped_column(String(64), default="rules-v1")
    prompt_version: Mapped[str] = mapped_column(String(64), default="tacit-profile-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
