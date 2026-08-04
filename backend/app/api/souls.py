from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import get_db
from app.services.soul_service import (
    confirm_soul,
    delete_soul_from_slot,
    draw_soul,
    get_inventory,
    get_templates,
    inject_soul,
    preview,
    recommend,
    save_soul_to_slot,
    seed_templates,
)

router = APIRouter(prefix="/api/souls", tags=["souls"])


class RecommendRequest(BaseModel):
    answers: list[dict]


class PreviewRequest(BaseModel):
    slug: str


class ConfirmRequest(BaseModel):
    template_id: str


class SaveSlotRequest(BaseModel):
    template_id: str
    replace_slot_id: str | None = None


class DrawRequest(BaseModel):
    exclude_template_id: str | None = None


@router.get("/templates")
async def api_get_templates(db: AsyncSession = Depends(get_db)):
    await seed_templates(db)
    return ok(await get_templates(db))


@router.post("/recommend")
async def api_recommend(req: RecommendRequest):
    return ok({"recommendations": recommend(req.answers)})


@router.post("/preview")
async def api_preview(req: PreviewRequest, db: AsyncSession = Depends(get_db)):
    return ok({"messages": await preview(req.slug, db)})


@router.post("/users/me/soul")
async def api_confirm_soul(req: ConfirmRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await confirm_soul(user_id, req.template_id, db)


@router.get("/me/inventory")
async def api_get_inventory(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return ok(await get_inventory(user_id, db))


@router.post("/me/draw")
async def api_draw_soul(
    req: DrawRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    exclude = req.exclude_template_id if req else None
    return await draw_soul(user_id, db, exclude)


@router.post("/me/slots/save")
async def api_save_slot(req: SaveSlotRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await save_soul_to_slot(user_id, req.template_id, req.replace_slot_id, db)


@router.delete("/me/slots/{slot_id}")
async def api_delete_slot(slot_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await delete_soul_from_slot(user_id, slot_id, db)


@router.post("/me/inject")
async def api_inject_soul(req: ConfirmRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    return await inject_soul(user_id, req.template_id, db)
