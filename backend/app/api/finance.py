from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok, fail
from app.db.session import get_db
from app.services import billing_service
from app.services import finance_service

router = APIRouter(prefix="/api/finance", tags=["finance"])


class CreateRecordRequest(BaseModel):
    type: str  # income / expense
    category: str
    amount: int  # 单位：分
    note: str = ""
    record_date: str | None = None
    source: str = "manual"


class UpdateRecordRequest(BaseModel):
    type: str | None = None
    category: str | None = None
    amount: int | None = None
    note: str | None = None
    record_date: str | None = None


class AiParseRequest(BaseModel):
    text: str


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    record_id: str | None = None


@router.post("/record")
async def api_create_record(req: CreateRecordRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    data = req.model_dump()
    if req.record_date:
        data["record_date"] = datetime.fromisoformat(req.record_date).date()
    else:
        data["record_date"] = datetime.now().date()
    result = await finance_service.create_record(user_id, data, db)
    return ok(result, "记账成功")


@router.get("/records")
async def api_get_records(year: int, month: int, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    records = await finance_service.get_records(user_id, year, month, db)
    return ok(records)


@router.put("/record/{record_id}")
async def api_update_record(record_id: str, req: UpdateRecordRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if "record_date" in data:
        data["record_date"] = datetime.fromisoformat(data["record_date"]).date()
    result = await finance_service.update_record(record_id, user_id, data, db)
    if not result:
        return fail("记录不存在")
    return ok(result, "修改成功")


@router.delete("/record/{record_id}")
async def api_delete_record(record_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    ok_ = await finance_service.delete_record(record_id, user_id, db)
    if not ok_:
        return fail("记录不存在")
    return ok(None, "已删除")


@router.get("/summary")
async def api_summary(year: int, month: int, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    result = await finance_service.get_summary(user_id, year, month, db)
    return ok(result)


@router.post("/ai-parse")
async def api_ai_parse(req: AiParseRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    # 计费：记账 AI 解析
    bill = await billing_service.consume(db, user_id, "finance_parse", ref_type="finance", note="记账AI解析")
    if bill.get("insufficient"):
        return fail(bill["message"])
    try:
        result = await finance_service.ai_parse(req.text)
        return ok(result)
    except Exception as e:
        return fail(f"解析失败: {e}")


@router.post("/messages")
async def api_save_message(req: SaveMessageRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    result = await finance_service.save_message(user_id, req.role, req.content, req.record_id, db)
    return ok(result)


@router.get("/messages")
async def api_get_messages(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    messages = await finance_service.get_messages(user_id, db)
    return ok(messages)
