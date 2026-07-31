from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin, BalanceTransaction, RedemptionCode, RedemptionUsage
from app.models.conversation import Message, Session
from app.models.user import User
from app.api.admin_auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
async def admin_dashboard(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    days: int = 7,
):
    # 时间范围：7 / 30 / 90 / 180 天
    days = min(max(days, 1), 180)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    range_start = today_start - timedelta(days=days - 1)

    # 用户数
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    today_new_users = (
        await db.execute(select(func.count(User.id)).where(User.created_at >= today_start))
    ).scalar() or 0

    # 会话 / 消息
    total_sessions = (await db.execute(select(func.count(Session.id)))).scalar() or 0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    today_messages = (
        await db.execute(select(func.count(Message.id)).where(Message.created_at >= today_start))
    ).scalar() or 0

    # 积分：累计充值 / 累计消费 / 已兑换
    total_recharged = (
        await db.execute(
            select(func.coalesce(func.sum(BalanceTransaction.change), 0)).where(BalanceTransaction.type.in_(["recharge", "admin"]))
        )
    ).scalar() or 0
    total_consumed = (
        await db.execute(
            select(func.coalesce(func.sum(-BalanceTransaction.change), 0)).where(
                BalanceTransaction.type == "consume"
            )
        )
    ).scalar() or 0
    redeemed_amount = (
        await db.execute(select(func.coalesce(func.sum(RedemptionUsage.amount), 0)))
    ).scalar() or 0
    active_codes = (
        await db.execute(select(func.count(RedemptionCode.id)).where(RedemptionCode.status == "active"))
    ).scalar() or 0

    # 趋势（供仪表盘"脉搏线"）：每日消息数 / 消费积分
    trend = []
    for i in range(days):
        day = range_start + timedelta(days=i)
        next_day = day + timedelta(days=1)
        msgs = (
            await db.execute(
                select(func.count(Message.id)).where(Message.created_at >= day, Message.created_at < next_day)
            )
        ).scalar() or 0
        consumed = (
            await db.execute(
                select(func.coalesce(func.sum(-BalanceTransaction.change), 0)).where(
                    BalanceTransaction.type == "consume",
                    BalanceTransaction.created_at >= day,
                    BalanceTransaction.created_at < next_day,
                )
            )
        ).scalar() or 0
        trend.append({"date": day.strftime("%m-%d"), "messages": msgs, "consumed": consumed})

    return {
        "success": True,
        "data": {
            "total_users": total_users,
            "today_new_users": today_new_users,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "today_messages": today_messages,
            "total_recharged": total_recharged,
            "total_consumed": total_consumed,
            "redeemed_amount": redeemed_amount,
            "active_codes": active_codes,
            "days": days,
            "trend": trend,
        },
    }
