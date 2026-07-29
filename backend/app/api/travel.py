from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok, fail
from app.db.session import get_db
from app.services import travel_service

router = APIRouter(prefix="/api/travel", tags=["travel"])


class GenerateRequest(BaseModel):
    destination: str
    start_date: str
    days: int
    budget: int = 0
    adults: int = 1
    children: int = 0
    preferences: list[str] = []
    note: str = ""


class UpdateRequest(BaseModel):
    title: str | None = None
    saved: bool | None = None


class RegenerateDayRequest(BaseModel):
    day_number: int


@router.post("/plan")
async def api_generate(req: GenerateRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    data = req.model_dump()
    data["user_id"] = user_id
    result = await travel_service.ai_generate(data, db)
    if "error" in result:
        return fail(result["error"])
    return ok(result, "行程已生成")


@router.get("/plans")
async def api_get_plans(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    plans = await travel_service.get_plans(user_id, db)
    return ok(plans)


@router.get("/plan/{plan_id}")
async def api_get_plan(plan_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    plan = await travel_service.get_plan(plan_id, user_id, db)
    if not plan:
        return fail("行程不存在")
    return ok(plan)


@router.put("/plan/{plan_id}")
async def api_update_plan(plan_id: str, req: UpdateRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await travel_service.update_plan(plan_id, user_id, data, db)
    if not result:
        return fail("行程不存在")
    return ok(result, "已更新")


@router.delete("/plan/{plan_id}")
async def api_delete_plan(plan_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    ok_ = await travel_service.delete_plan(plan_id, user_id, db)
    if not ok_:
        return fail("行程不存在")
    return ok(None, "已删除")


@router.post("/plan/{plan_id}/regenerate-day")
async def api_regenerate_day(plan_id: str, req: RegenerateDayRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    result = await travel_service.regenerate_day(plan_id, user_id, req.day_number, db)
    if not result:
        return fail("生成失败")
    return ok(result, "已更新")
