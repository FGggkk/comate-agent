import re
import uuid

from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import Admin
from app.models.soul import SoulTemplate
from app.api.admin_auth import get_current_admin
from app.services import cos_service

router = APIRouter(prefix="/api/admin/souls", tags=["admin"])


@router.post("/upload")
async def upload_soul_image(
    file: UploadFile = File(...),
    admin: Admin = Depends(get_current_admin),
):
    """上传角色图片（卡面图/头像图），返回 URL"""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        return {"success": False, "message": "图片不能超过 5MB"}
    url = cos_service.upload_image(content, file.filename or "soul.png", folder="souls")
    if not url:
        return {"success": False, "message": "上传失败（COS 未配置或出错）"}
    return {"success": True, "url": url}


class CreateSoulRequest(BaseModel):
    name: str
    description: str = ""
    slug: str | None = None
    color: str | None = None
    tags: list[str] = []
    soul_markdown: str
    dimensions: dict = {}
    card_image: str | None = None
    avatar_image: str | None = None


class UpdateSoulRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    tags: list[str] | None = None
    soul_markdown: str | None = None
    dimensions: dict | None = None
    card_image: str | None = None
    avatar_image: str | None = None


class ImportSoulRequest(BaseModel):
    text: str  # SOUL.md 文本（含 frontmatter）


class StatusRequest(BaseModel):
    status: str  # active / inactive


class SortRequest(BaseModel):
    sort_order: int


def _soul_dict(t: SoulTemplate) -> dict:
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "description": t.description,
        "dimensions": t.dimensions or {},
        "soul_markdown": t.soul_markdown,
        "version": t.version,
        "status": t.status,
        "tags": t.tags or [],
        "color": t.color,
        "card_image": t.card_image,
        "avatar_image": t.avatar_image,
        "sort_order": t.sort_order,
        "source": t.source,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _gen_slug(name: str) -> str:
    """从名称生成 slug：小写字母数字 + 短横线，加随机后缀防冲突"""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "soul"
    return f"{base[:30]}-{uuid.uuid4().hex[:6]}"


def _parse_soul_markdown(text: str) -> dict:
    """解析 SOUL.md：frontmatter（--- 包裹的 yaml 子集）+ 正文"""
    md = text.strip()
    meta: dict = {}
    body = md
    if md.startswith("---"):
        parts = md.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].strip()
            for line in fm.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k == "tags":
                        meta["tags"] = [x.strip().strip("'\"[]") for x in v.replace("[", "").replace("]", "").split(",") if x.strip()]
                    elif k in ("color", "name", "slug", "description"):
                        meta[k] = v
                    elif k in ("card_image", "avatar_image"):
                        meta[k] = v
    return {"meta": meta, "body": body}


@router.get("")
async def list_souls(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    status: str = "all",
    q: str = "",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    stmt = select(SoulTemplate).order_by(SoulTemplate.sort_order, SoulTemplate.created_at)
    count_stmt = select(func.count(SoulTemplate.id))
    if status and status != "all":
        stmt = stmt.where(SoulTemplate.status == status)
        count_stmt = count_stmt.where(SoulTemplate.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((SoulTemplate.name.ilike(like)) | (SoulTemplate.slug.ilike(like)))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.offset((page - 1) * size).limit(size))).scalars().all()
    return {"success": True, "data": {"items": [_soul_dict(t) for t in rows], "total": total, "page": page}}


@router.post("")
async def create_soul(
    req: CreateSoulRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if not req.name.strip() or not req.soul_markdown.strip():
        return {"success": False, "message": "名称和角色设定不能为空"}
    slug = req.slug or _gen_slug(req.name)
    existing = (await db.execute(select(SoulTemplate).where(SoulTemplate.slug == slug))).scalar_one_or_none()
    if existing:
        slug = _gen_slug(req.name)
    t = SoulTemplate(
        slug=slug,
        name=req.name.strip(),
        description=req.description,
        dimensions=req.dimensions or {},
        soul_markdown=req.soul_markdown.strip(),
        tags=req.tags or [],
        color=req.color,
        card_image=req.card_image,
        avatar_image=req.avatar_image,
        sort_order=0,
        source="custom",
        created_by=admin.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"success": True, "message": "角色已创建", "soul": _soul_dict(t)}


@router.post("/import")
async def import_soul(
    req: ImportSoulRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """从 SOUL.md 文本导入（支持 skillhub 等导出格式的 frontmatter）"""
    parsed = _parse_soul_markdown(req.text)
    meta = parsed["meta"]
    body = parsed["body"]
    name = meta.get("name") or (body.splitlines()[0].lstrip("# ").strip() if body else "")
    if not name:
        return {"success": False, "message": "无法解析角色名称（frontmatter 需含 name）"}
    slug = meta.get("slug") or _gen_slug(name)
    existing = (await db.execute(select(SoulTemplate).where(SoulTemplate.slug == slug))).scalar_one_or_none()
    if existing:
        slug = _gen_slug(name)
    t = SoulTemplate(
        slug=slug,
        name=name,
        description=meta.get("description", ""),
        dimensions={},
        soul_markdown=body or req.text.strip(),
        tags=meta.get("tags", []),
        color=meta.get("color"),
        card_image=meta.get("card_image"),
        avatar_image=meta.get("avatar_image"),
        sort_order=0,
        source="imported",
        created_by=admin.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"success": True, "message": f"已导入角色「{t.name}」", "soul": _soul_dict(t)}


@router.put("/{soul_id}")
async def update_soul(
    soul_id: str,
    req: UpdateSoulRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    t = (await db.execute(select(SoulTemplate).where(SoulTemplate.id == soul_id))).scalar_one_or_none()
    if not t:
        return {"success": False, "message": "角色不存在"}
    if req.name is not None:
        t.name = req.name.strip()
    if req.description is not None:
        t.description = req.description
    if req.color is not None:
        t.color = req.color
    if req.tags is not None:
        t.tags = req.tags
    if req.soul_markdown is not None:
        t.soul_markdown = req.soul_markdown.strip()
    if req.dimensions is not None:
        t.dimensions = req.dimensions
    if req.card_image is not None:
        t.card_image = req.card_image
    if req.avatar_image is not None:
        t.avatar_image = req.avatar_image
    t.updated_at = func.now()
    await db.commit()
    await db.refresh(t)
    return {"success": True, "message": "角色已更新", "soul": _soul_dict(t)}


@router.post("/{soul_id}/status")
async def update_status(
    soul_id: str,
    req: StatusRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if req.status not in ("active", "inactive"):
        return {"success": False, "message": "状态非法"}
    t = (await db.execute(select(SoulTemplate).where(SoulTemplate.id == soul_id))).scalar_one_or_none()
    if not t:
        return {"success": False, "message": "角色不存在"}
    t.status = req.status
    await db.commit()
    return {"success": True, "message": "已" + ("上架" if req.status == "active" else "下架")}


@router.put("/{soul_id}/sort")
async def update_sort(
    soul_id: str,
    req: SortRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    t = (await db.execute(select(SoulTemplate).where(SoulTemplate.id == soul_id))).scalar_one_or_none()
    if not t:
        return {"success": False, "message": "角色不存在"}
    t.sort_order = req.sort_order
    await db.commit()
    return {"success": True, "message": "排序已更新"}
