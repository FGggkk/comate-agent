from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin, AppSetting, BillingRule
from app.api.admin_auth import get_current_admin
from app.services import billing_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RuleUpdate(BaseModel):
    item_key: str
    price: int
    enabled: bool


class RulesSaveRequest(BaseModel):
    rules: list[RuleUpdate]


class SettingUpdate(BaseModel):
    key: str
    value: str


def _rule_dict(r: BillingRule) -> dict:
    return {"item_key": r.item_key, "item_name": r.item_name, "price": r.price, "enabled": r.enabled}


@router.get("/billing-rules")
async def get_rules(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    rules = (await db.execute(select(BillingRule).order_by(BillingRule.price.desc()))).scalars().all()
    enforce = await billing_service.get_setting(db, "billing_enforce", "false")
    bonus = await billing_service.get_setting(db, "register_bonus", "20")
    # 系统设置
    settings_keys = [
        "model_key", "model_name", "model_temperature",
        "tool_search", "tool_weather", "tool_shopping",
    ]
    settings = {k: await billing_service.get_setting(db, k, "") for k in settings_keys}
    return {
        "success": True,
        "data": {
            "rules": [_rule_dict(r) for r in rules],
            "billing_enforce": enforce,
            "register_bonus": bonus,
            "settings": settings,
        },
    }


@router.put("/billing-rules")
async def save_rules(
    req: RulesSaveRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    for item in req.rules:
        rule = (
            await db.execute(select(BillingRule).where(BillingRule.item_key == item.item_key))
        ).scalar_one_or_none()
        if not rule:
            continue
        rule.price = max(0, item.price)
        rule.enabled = item.enabled
    await db.commit()
    return {"success": True, "message": "计费规则已保存"}


@router.put("/settings")
async def save_setting(
    req: SettingUpdate,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    allowed = {
        "billing_enforce", "register_bonus",
        "model_key", "model_name", "model_temperature",
        "tool_search", "tool_weather", "tool_shopping",
    }
    if req.key not in allowed:
        return {"success": False, "message": "不支持的设置项"}
    if req.key == "register_bonus" or req.key == "model_temperature":
        try:
            float(req.value)
        except ValueError:
            return {"success": False, "message": "数值格式不正确"}
    await billing_service.set_setting(db, req.key, req.value)
    return {"success": True, "message": "已保存"}
