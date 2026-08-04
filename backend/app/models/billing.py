import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .user import Base


class Admin(Base):
    """管理员账号（与用户端隔离）"""
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="admin")  # admin / super
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RedemptionCode(Base):
    """兑换码"""
    __tablename__ = "redemption_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 面额（积分）
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 批次号
    max_uses: Mapped[int] = mapped_column(Integer, default=1)  # 可兑换次数
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / disabled / expired
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RedemptionUsage(Base):
    """兑换记录"""
    __tablename__ = "redemption_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("redemption_codes.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BalanceAccount(Base):
    """用户积分余额账户"""
    __tablename__ = "balance_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    balance: Mapped[int] = mapped_column(Integer, default=0)  # 当前余额（积分）
    total_recharged: Mapped[int] = mapped_column(Integer, default=0)  # 累计充值
    total_consumed: Mapped[int] = mapped_column(Integer, default=0)  # 累计消费
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BalanceTransaction(Base):
    """余额流水"""
    __tablename__ = "balance_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    change: Mapped[int] = mapped_column(Integer, nullable=False)  # 变动（正=入账，负=扣减）
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # recharge / consume / admin
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # redemption_code / chat / interview / shopping / travel / finance / admin_adjust
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BillingRule(Base):
    """计费规则"""
    __tablename__ = "billing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # chat_round / interview_question ...
    item_name: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0)  # 单价（积分）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AppSetting(Base):
    """系统设置（键值对）：注册赠送积分 / 扣费模式等"""
    __tablename__ = "app_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
