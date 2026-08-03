from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin, BalanceAccount, BalanceTransaction
from app.models.soul import UserSoul
from app.models.user import User
from app.api.admin_auth import get_current_admin
from app.services import billing_service

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


class StatusRequest(BaseModel):
    status: str  # active / disabled


class BalanceRequest(BaseModel):
    change: int
    note: str | None = None


class SlotCapacityRequest(BaseModel):
    capacity: int  # 6 / 9 / 12


def _user_brief(u: User, balance: int | None = None) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "status": getattr(u, "status", "active") or "active",
        "slot_capacity": u.slot_capacity or 6,
        "balance": balance if balance is not None else 0,
        "onboarding_status": u.onboarding_status,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    }


@router.get("")
async def list_users(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    q: str = "",
    status: str = "all",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    stmt = select(User).order_by(User.created_at.desc())
    count_stmt = select(func.count(User.id))
    if status and status != "all":
        stmt = stmt.where(User.status == status)
        count_stmt = count_stmt.where(User.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.email.ilike(like)) | (User.nickname.ilike(like)))
    total = (await db.execute(count_stmt)).scalar() or 0
    users = (await db.execute(stmt.offset((page - 1) * size).limit(size))).scalars().all()

    # 批量取余额
    ids = [u.id for u in users]
    balances: dict[str, int] = {}
    if ids:
        accs = (
            await db.execute(select(BalanceAccount).where(BalanceAccount.user_id.in_(ids)))
        ).scalars().all()
        balances = {str(a.user_id): a.balance for a in accs}

    return {
        "success": True,
        "data": {
            "items": [_user_brief(u, balances.get(str(u.id), 0)) for u in users],
            "total": total,
            "page": page,
        },
    }


@router.get("/{user_id}")
async def user_detail(
    user_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return {"success": False, "message": "用户不存在"}

    balance = await billing_service.get_balance(db, user_id)
    # SOUL 库存
    souls = (
        await db.execute(
            select(UserSoul).where(UserSoul.user_id == user_id).order_by(UserSoul.created_at.desc())
        )
    ).scalars().all()
    # 最近流水 10 条
    txs = (
        await db.execute(
            select(BalanceTransaction)
            .where(BalanceTransaction.user_id == user_id)
            .order_by(BalanceTransaction.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return {
        "success": True,
        "data": {
            **_user_brief(user, balance),
            "souls": [{"id": str(s.id), "template_id": str(s.template_id), "status": s.status} for s in souls],
            "transactions": [
                {
                    "id": str(t.id),
                    "change": t.change,
                    "balance_after": t.balance_after,
                    "type": t.type,
                    "note": t.note,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in txs
            ],
        },
    }


@router.post("/{user_id}/status")
async def update_status(
    user_id: str,
    req: StatusRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return {"success": False, "message": "用户不存在"}
    if req.status not in ("active", "disabled"):
        return {"success": False, "message": "状态非法"}
    user.status = req.status
    await db.commit()
    return {"success": True, "message": "已" + ("禁用" if req.status == "disabled" else "启用")}


@router.post("/{user_id}/slot_capacity")
async def update_slot_capacity(
    user_id: str,
    req: SlotCapacityRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员设置用户灵魂卡槽上限（4/8/12）"""
    if req.capacity not in (6, 9, 12):
        return {"success": False, "message": "卡槽上限只能是 6 / 9 / 12"}
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return {"success": False, "message": "用户不存在"}
    user.slot_capacity = req.capacity
    await db.commit()
    return {"success": True, "message": f"卡槽上限已设为 {req.capacity}"}


@router.post("/{user_id}/balance")
async def adjust_balance(
    user_id: str,
    req: BalanceRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员调整余额（正=充值，负=扣减），写审计流水"""
    if req.change == 0:
        return {"success": False, "message": "变动不能为 0"}

    acc = (
        await db.execute(select(BalanceAccount).where(BalanceAccount.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if not acc:
        acc = BalanceAccount(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
        db.add(acc)
        await db.flush()

    new_balance = acc.balance + req.change
    if new_balance < 0:
        return {"success": False, "message": "调整后余额不能为负"}

    acc.balance = new_balance
    if req.change > 0:
        acc.total_recharged += req.change
    else:
        acc.total_consumed += -req.change
    db.add(
        BalanceTransaction(
            user_id=user_id,
            change=req.change,
            balance_after=new_balance,
            type="admin",
            ref_type="admin_adjust",
            note=f"管理员调整：{req.note or ''}",
        )
    )
    await db.commit()
    return {"success": True, "balance": new_balance, "message": f"已调整 {req.change:+d} 积分"}
