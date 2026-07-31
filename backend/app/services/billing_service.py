import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    AppSetting,
    BalanceAccount,
    BalanceTransaction,
    BillingRule,
    RedemptionCode,
    RedemptionUsage,
)

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉 I/O/0/1 易混淆字符


def _gen_code() -> str:
    """生成兑换码：BANX-XXXX-XXXX-XXXX"""
    groups = ["".join(random.choices(CODE_CHARS, k=4)) for _ in range(3)]
    return f"BANX-{'-'.join(groups)}"


def _code_to_dict(c: RedemptionCode) -> dict:
    now = datetime.now(timezone.utc)
    if c.status == "active" and c.expires_at and c.expires_at < now:
        status = "expired"
    else:
        status = c.status
    if status == "active" and c.used_count >= c.max_uses:
        status = "used"
    return {
        "id": str(c.id),
        "code": c.code,
        "amount": c.amount,
        "batch_no": c.batch_no,
        "max_uses": c.max_uses,
        "used_count": c.used_count,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "status": status,
        "note": c.note,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ==================== 兑换码生成（管理端） ====================

async def generate_codes(
    db: AsyncSession,
    amount: int,
    count: int,
    expires_days: int | None,
    max_uses: int,
    note: str | None,
    created_by,
) -> list[RedemptionCode]:
    """批量生成兑换码（最多 500 个/次），自动去重"""
    codes: list[RedemptionCode] = []
    existing = set()
    result = await db.execute(select(RedemptionCode.code))
    existing = {r[0] for r in result.fetchall()}

    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    batch_no = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{random.randint(100, 999)}"
    generated = 0
    attempts = 0
    while generated < count and attempts < count * 10:
        attempts += 1
        code = _gen_code()
        if code in existing:
            continue
        existing.add(code)
        codes.append(
            RedemptionCode(
                code=code,
                amount=amount,
                batch_no=batch_no,
                max_uses=max_uses,
                expires_at=expires_at,
                note=note,
                created_by=created_by,
            )
        )
        generated += 1

    db.add_all(codes)
    await db.commit()
    for c in codes:
        await db.refresh(c)
    return codes


# ==================== 兑换（用户端，事务） ====================

async def redeem_code(db: AsyncSession, code_str: str, user_id: str) -> dict:
    """兑换码入账：校验 + 幂等 + 限量（行锁）+ 余额流水，全部在事务内"""
    code_str = code_str.strip().upper()
    result = await db.execute(
        select(RedemptionCode)
        .where(RedemptionCode.code == code_str)
        .with_for_update()
    )
    code = result.scalar_one_or_none()
    if not code:
        return {"success": False, "message": "兑换码不存在"}

    now = datetime.now(timezone.utc)
    if code.status != "active":
        return {"success": False, "message": "兑换码已失效"}
    if code.expires_at and code.expires_at < now:
        code.status = "expired"
        await db.commit()
        return {"success": False, "message": "兑换码已过期"}
    if code.used_count >= code.max_uses:
        return {"success": False, "message": "兑换码已被使用完"}

    # 幂等：同码同用户只能兑换一次
    usage = await db.execute(
        select(RedemptionUsage).where(
            RedemptionUsage.code_id == code.id,
            RedemptionUsage.user_id == user_id,
        )
    )
    if usage.scalar_one_or_none():
        return {"success": False, "message": "该兑换码已兑换过"}

    # 余额账户（无则创建）
    acc = (
        await db.execute(
            select(BalanceAccount).where(BalanceAccount.user_id == user_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not acc:
        acc = BalanceAccount(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
        db.add(acc)
        await db.flush()

    acc.balance += code.amount
    acc.total_recharged += code.amount
    code.used_count += 1
    if code.used_count >= code.max_uses:
        code.status = "used"

    db.add(
        RedemptionUsage(code_id=code.id, user_id=user_id, amount=code.amount)
    )
    db.add(
        BalanceTransaction(
            user_id=user_id,
            change=code.amount,
            balance_after=acc.balance,
            type="recharge",
            ref_type="redemption_code",
            ref_id=str(code.id),
            note=f"兑换码 {code.code}",
        )
    )
    await db.commit()
    return {"success": True, "message": f"兑换成功 +{code.amount} 积分", "balance": acc.balance}


# ==================== 余额 / 流水（用户端） ====================

async def get_balance(db: AsyncSession, user_id: str) -> int:
    acc = (
        await db.execute(select(BalanceAccount).where(BalanceAccount.user_id == user_id))
    ).scalar_one_or_none()
    return acc.balance if acc else 0


async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    s = result.scalar_one_or_none()
    return s.value if s else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    s = result.scalar_one_or_none()
    if s:
        s.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    await db.commit()


# ==================== 消费扣费（严格/宽松） ====================

async def consume(
    db: AsyncSession,
    user_id: str,
    item_key: str,
    ref_type: str | None = None,
    ref_id: str | None = None,
    note: str | None = None,
) -> dict:
    """按计费规则扣费。
    - 规则关闭(enabled=False) 或 单价 0 → 跳过不扣
    - 宽松模式(billing_enforce=false)：余额不足也扣（允许负余额）
    - 严格模式(billing_enforce=true)：余额不足返回 insufficient
    """
    rule = (
        await db.execute(select(BillingRule).where(BillingRule.item_key == item_key))
    ).scalar_one_or_none()
    if not rule or not rule.enabled or rule.price <= 0:
        return {"success": True, "skipped": True, "price": 0}

    acc = (
        await db.execute(select(BalanceAccount).where(BalanceAccount.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if not acc:
        acc = BalanceAccount(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
        db.add(acc)
        await db.flush()

    enforce = (await get_setting(db, "billing_enforce", "false")) == "true"
    if enforce and acc.balance < rule.price:
        await db.rollback()
        return {
            "success": False,
            "insufficient": True,
            "balance": acc.balance,
            "price": rule.price,
            "message": f"积分不足，需要 {rule.price} 积分（当前 {acc.balance}）",
        }

    new_balance = acc.balance - rule.price
    acc.balance = new_balance
    acc.total_consumed += rule.price
    db.add(
        BalanceTransaction(
            user_id=user_id,
            change=-rule.price,
            balance_after=new_balance,
            type="consume",
            ref_type=ref_type or item_key,
            ref_id=ref_id,
            note=note or rule.item_name,
        )
    )
    await db.commit()
    return {"success": True, "price": rule.price, "balance": new_balance, "skipped": False}


# ==================== 注册赠送 ====================

async def grant_register_bonus(db: AsyncSession, user_id: str) -> int:
    """新用户注册赠送积分（app_settings.register_bonus 可配置，0 表示不送）"""
    bonus = int((await get_setting(db, "register_bonus", "20")) or 0)
    if bonus <= 0:
        return 0
    acc = (
        await db.execute(select(BalanceAccount).where(BalanceAccount.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if not acc:
        acc = BalanceAccount(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
        db.add(acc)
        await db.flush()
    acc.balance += bonus
    acc.total_recharged += bonus
    db.add(
        BalanceTransaction(
            user_id=user_id,
            change=bonus,
            balance_after=acc.balance,
            type="recharge",
            ref_type="register_bonus",
            note="注册赠送",
        )
    )
    await db.commit()
    return bonus


async def get_transactions(db: AsyncSession, user_id: str, page: int = 1, size: int = 20) -> dict:
    result = await db.execute(
        select(BalanceTransaction)
        .where(BalanceTransaction.user_id == user_id)
        .order_by(BalanceTransaction.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    total = (
        await db.execute(
            select(func.count(BalanceTransaction.id)).where(BalanceTransaction.user_id == user_id)
        )
    ).scalar() or 0
    items = [
        {
            "id": str(t.id),
            "change": t.change,
            "balance_after": t.balance_after,
            "type": t.type,
            "ref_type": t.ref_type,
            "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page}


# ==================== 管理端：列表 / 作废 / 导出 ====================

async def list_codes(db: AsyncSession, status: str | None = None, q: str = "", page: int = 1, size: int = 20) -> dict:
    stmt = select(RedemptionCode).order_by(RedemptionCode.created_at.desc())
    count_stmt = select(func.count(RedemptionCode.id))
    if status and status != "all":
        if status == "expired":
            stmt = stmt.where(RedemptionCode.status.in_(["active", "used"])).where(
                RedemptionCode.expires_at < datetime.now(timezone.utc)
            )
        else:
            stmt = stmt.where(RedemptionCode.status == status)
        count_stmt = count_stmt.where(RedemptionCode.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (RedemptionCode.code.ilike(like)) | (RedemptionCode.batch_no.ilike(like))
        )
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.offset((page - 1) * size).limit(size))
    return {
        "items": [_code_to_dict(c) for c in result.scalars().all()],
        "total": total,
        "page": page,
    }


async def disable_code(db: AsyncSession, code_id: str) -> bool:
    result = await db.execute(
        update(RedemptionCode)
        .where(RedemptionCode.id == code_id, RedemptionCode.status == "active")
        .values(status="disabled")
    )
    await db.commit()
    return result.rowcount > 0


async def get_code_usage(db: AsyncSession, code_id: str) -> list[dict]:
    result = await db.execute(
        select(RedemptionUsage)
        .where(RedemptionUsage.code_id == code_id)
        .order_by(RedemptionUsage.redeemed_at.desc())
    )
    return [
        {
            "id": str(u.id),
            "user_id": str(u.user_id),
            "amount": u.amount,
            "redeemed_at": u.redeemed_at.isoformat() if u.redeemed_at else None,
        }
        for u in result.scalars().all()
    ]


async def export_codes_csv(db: AsyncSession, batch_no: str | None = None) -> tuple[str, str]:
    """导出兑换码 CSV，返回 (csv内容, 文件名)"""
    stmt = select(RedemptionCode).order_by(RedemptionCode.created_at.desc())
    if batch_no:
        stmt = stmt.where(RedemptionCode.batch_no == batch_no)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    lines = ["兑换码,面额,状态,有效期,备注"]
    for c in rows:
        d = _code_to_dict(c)
        lines.append(f"{c.code},{c.amount},{d['status']},{d['expires_at'] or ''},{c.note or ''}")
    content = "\n".join(lines)
    filename = f"redemption-codes-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}.csv"
    return content, filename
