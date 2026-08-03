from fastapi import APIRouter, Depends

from app.api.admin_auth import get_current_admin
from app.api.response import ok
from app.models.billing import Admin
from app.plugins.company_knowledge.registry import list_knowledge_types


router = APIRouter(prefix="/api/admin/company-knowledge", tags=["admin"])


@router.get("/types")
async def list_admin_types(admin: Admin = Depends(get_current_admin)):
    """管理端使用同一资料类型注册表，不在页面中分散维护枚举。"""
    return ok({"items": list_knowledge_types()})
