import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .user import Base


class TravelPlan(Base):
    __tablename__ = "travel_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="")
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    budget: Mapped[int] = mapped_column(Integer, default=0)  # 分
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)
    preferences: Mapped[list] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text, default="")
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TravelDay(Base):
    __tablename__ = "travel_days"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("travel_plans.id", ondelete="CASCADE"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    segments: Mapped[list] = mapped_column(JSONB, default=list)
    total_cost: Mapped[int] = mapped_column(Integer, default=0)
