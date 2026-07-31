from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin
from app.api.admin_auth import get_current_admin
from app.services import billing_service

router = APIRouter(prefix="/api/admin/codes", tags=["admin"])


class GenerateRequest(BaseModel):
    amount: int = Field(gt=0, le=100000, description="面额（积分）")
    count: int = Field(gt=0, le=500, description="生成数量")
    expires_days: int | None = Field(default=None, ge=1, le=3650)
    max_uses: int = Field(default=1, ge=1, le=1000)
    note: str | None = None


@router.get("")
async def list_codes(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    status: str = "all",
    q: str = "",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    data = await billing_service.list_codes(db, status, q, page, size)
    return {"success": True, "data": data}


@router.post("/generate")
async def generate_codes(
    req: GenerateRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    codes = await billing_service.generate_codes(
        db, req.amount, req.count, req.expires_days, req.max_uses, req.note, admin.id
    )
    return {
        "success": True,
        "data": {
            "batch_no": codes[0].batch_no if codes else None,
            "count": len(codes),
            "codes": [billing_service._code_to_dict(c) for c in codes],
        },
    }


@router.get("/export")
async def export_codes(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    batch_no: str | None = None,
):
    content, filename = await billing_service.export_codes_csv(db, batch_no)
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{code_id}/disable")
async def disable_code(
    code_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ok = await billing_service.disable_code(db, code_id)
    if not ok:
        return {"success": False, "message": "作废失败（可能已失效）"}
    return {"success": True, "message": "已作废"}


@router.get("/{code_id}/usage")
async def code_usage(
    code_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await billing_service.get_code_usage(db, code_id)
    return {"success": True, "data": data}
