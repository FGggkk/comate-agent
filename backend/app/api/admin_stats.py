from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin, BalanceTransaction, RedemptionUsage
from app.models.conversation import Message
from app.models.finance import FinanceRecord
from app.models.interview import InterviewSession
from app.models.shopping import ShoppingPlan
from app.models.travel import TravelPlan
from app.models.user import User
from app.api.admin_auth import get_current_admin

router = APIRouter(prefix="/api/admin/stats", tags=["admin"])


@router.get("")
async def admin_stats(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    days: int = 30,
):
    days = min(max(days, 1), 180)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    range_start = today_start - timedelta(days=days - 1)

    # 1. 工具使用量（各表累计）
    interview_count = (await db.execute(select(func.count(InterviewSession.id)))).scalar() or 0
    travel_count = (await db.execute(select(func.count(TravelPlan.id)))).scalar() or 0
    shopping_count = (await db.execute(select(func.count(ShoppingPlan.id)))).scalar() or 0
    finance_count = (await db.execute(select(func.count(FinanceRecord.id)))).scalar() or 0
    tool_usage = [
        {"name": "面试训练", "key": "interview", "count": interview_count},
        {"name": "旅游规划", "key": "travel", "count": travel_count},
        {"name": "购物计划", "key": "shopping", "count": shopping_count},
        {"name": "记账", "key": "finance", "count": finance_count},
    ]

    # 2. 消费分布（按 ref_type 汇总 consume 流水）
    dist_rows = (
        await db.execute(
            select(
                BalanceTransaction.ref_type,
                func.coalesce(func.sum(-BalanceTransaction.change), 0),
            )
            .where(
                BalanceTransaction.type == "consume",
                BalanceTransaction.created_at >= range_start,
            )
            .group_by(BalanceTransaction.ref_type)
        )
    ).fetchall()
    consume_distribution = [{"key": k or "other", "amount": int(v)} for k, v in dist_rows]

    # 3. 兑换趋势（近 days 天，按天）
    redeem_rows = (
        await db.execute(
            select(RedemptionUsage.redeemed_at, RedemptionUsage.amount)
            .where(RedemptionUsage.redeemed_at >= range_start)
        )
    ).fetchall()
    redeem_map: dict[str, int] = {}
    for redeemed_at, amount in redeem_rows:
        key = redeemed_at.strftime("%m-%d")
        redeem_map[key] = redeem_map.get(key, 0) + int(amount)

    # 4. 用户增长（近 days 天，按天）
    user_rows = (
        await db.execute(
            select(User.created_at).where(User.created_at >= range_start)
        )
    ).fetchall()
    user_map: dict[str, int] = {}
    for (created_at,) in user_rows:
        key = created_at.strftime("%m-%d")
        user_map[key] = user_map.get(key, 0) + 1

    # 5. 对话量趋势（近 days 天，按天）
    msg_rows = (
        await db.execute(
            select(Message.created_at).where(Message.created_at >= range_start)
        )
    ).fetchall()
    msg_map: dict[str, int] = {}
    for (created_at,) in msg_rows:
        key = created_at.strftime("%m-%d")
        msg_map[key] = msg_map.get(key, 0) + 1

    # 组装日期序列
    dates = [(range_start + timedelta(days=i)).strftime("%m-%d") for i in range(days)]
    redemption_trend = [{"date": d, "amount": redeem_map.get(d, 0)} for d in dates]
    user_growth = [{"date": d, "count": user_map.get(d, 0)} for d in dates]
    chat_trend = [{"date": d, "count": msg_map.get(d, 0)} for d in dates]

    return {
        "success": True,
        "data": {
            "days": days,
            "tool_usage": tool_usage,
            "consume_distribution": consume_distribution,
            "redemption_trend": redemption_trend,
            "user_growth": user_growth,
            "chat_trend": chat_trend,
        },
    }
