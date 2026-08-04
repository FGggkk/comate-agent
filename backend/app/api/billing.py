from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services import billing_service

router = APIRouter(prefix="/api/billing", tags=["billing"])


class RedeemRequest(BaseModel):
    code: str


@router.post("/redeem")
async def redeem(
    req: RedeemRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.redeem_code(db, req.code, user_id)


@router.get("/balance")
async def balance(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bal = await billing_service.get_balance(db, user_id)
    return {"success": True, "balance": bal}


@router.get("/transactions")
async def transactions(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    data = await billing_service.get_transactions(db, user_id, page, size)
    return {"success": True, "data": data}
