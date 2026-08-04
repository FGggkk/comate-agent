from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import FinanceMessage, FinanceRecord


async def create_record(user_id: str, data: dict, db: AsyncSession) -> dict:
    record = FinanceRecord(
        user_id=user_id,
        type=data["type"],
        category=data["category"],
        amount=data["amount"],
        note=data.get("note", ""),
        record_date=data.get("record_date", datetime.now(timezone.utc).date()),
        source=data.get("source", "manual"),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _record_to_dict(record)


async def get_records(user_id: str, year: int, month: int, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(FinanceRecord).where(
            FinanceRecord.user_id == user_id,
            func.extract("year", FinanceRecord.record_date) == year,
            func.extract("month", FinanceRecord.record_date) == month,
        ).order_by(FinanceRecord.record_date.desc(), FinanceRecord.created_at.desc())
    )
    return [_record_to_dict(r) for r in result.scalars().all()]


async def update_record(record_id: str, user_id: str, data: dict, db: AsyncSession) -> dict | None:
    result = await db.execute(
        select(FinanceRecord).where(FinanceRecord.id == record_id, FinanceRecord.user_id == user_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None
    for key in ("type", "category", "amount", "note", "record_date"):
        if key in data:
            setattr(record, key, data[key])
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return _record_to_dict(record)


async def delete_record(record_id: str, user_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(FinanceRecord).where(FinanceRecord.id == record_id, FinanceRecord.user_id == user_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return False
    await db.delete(record)
    await db.commit()
    return True


async def get_summary(user_id: str, year: int, month: int, db: AsyncSession) -> dict:
    records = await get_records(user_id, year, month, db)
    total_income = sum(r["amount"] for r in records if r["type"] == "income")
    total_expense = sum(r["amount"] for r in records if r["type"] == "expense")
    categories = {}
    for r in records:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"amount": 0, "type": r["type"]}
        categories[cat]["amount"] += r["amount"]
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "categories": [{"name": k, "amount": v["amount"], "type": v["type"]} for k, v in categories.items()],
    }


async def save_message(user_id: str, role: str, content: str, record_id: str | None, db: AsyncSession) -> dict:
    msg = FinanceMessage(user_id=user_id, role=role, content=content, record_id=record_id)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {"id": str(msg.id), "role": msg.role, "content": msg.content, "record_id": str(msg.record_id) if msg.record_id else None, "created_at": msg.created_at.isoformat()}


async def get_messages(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(FinanceMessage).where(FinanceMessage.user_id == user_id).order_by(FinanceMessage.created_at.asc()).limit(100)
    )
    return [
        {"id": str(m.id), "role": m.role, "content": m.content, "record_id": str(m.record_id) if m.record_id else None, "created_at": m.created_at.isoformat()}
        for m in result.scalars().all()
    ]


async def ai_parse(text: str) -> dict:
    from app.services.model_gateway import gateway
    prompt = f"""从用户的记账输入中提取信息，返回JSON。

输入：{text}

要求提取：
- amount: 金额（单位：分，整数。如32元→3200）
- type: "income" 或 "expense"
- category: 从以下选择最合适的（餐饮/交通/购物/居住/娱乐/其他支出/薪资/其他收入）
- note: 备注说明（简洁）

只返回JSON，不要多余文字。
{{
  "amount": 3200,
  "type": "expense",
  "category": "餐饮",
  "note": "中午吃饭"
}}"""
    full = ""
    async for chunk in gateway.stream(prompt):
        full += chunk
    import json
    full = full.strip().strip("```json").strip("```").strip()
    try:
        return json.loads(full)
    except json.JSONDecodeError:
        return {"amount": 0, "type": "expense", "category": "其他支出", "note": text}


def _record_to_dict(r: FinanceRecord) -> dict:
    return {
        "id": str(r.id),
        "type": r.type,
        "category": r.category,
        "amount": r.amount,
        "note": r.note or "",
        "record_date": r.record_date.isoformat() if r.record_date else None,
        "source": r.source,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
