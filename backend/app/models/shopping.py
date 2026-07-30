"""购物计划模型"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Text, UUID, text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


class ShoppingPlan(Base):
    __tablename__ = "shopping_plans"

    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID, nullable=False, index=True)
    demand = Column(Text, nullable=False)
    plans = Column(JSONB, nullable=False)
    favorited = Column(Text, server_default=text("'false'"))
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
    )
