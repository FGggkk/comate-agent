from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.response import fail, ok
from app.plugins.company_knowledge.registry import get_knowledge_type, is_query_enabled, list_knowledge_types
from app.plugins.company_knowledge.schemas import CompanyKnowledgeQueryRequest


router = APIRouter(prefix="/api/company-knowledge", tags=["company-knowledge"])


@router.get("/types")
async def list_types(user_id: str = Depends(get_current_user)):
    """返回所有已注册资料类型，供前端按可用状态组织入口。"""
    return ok({"items": list_knowledge_types()})


@router.post("/query")
async def query_company_knowledge(
    req: CompanyKnowledgeQueryRequest,
    user_id: str = Depends(get_current_user),
):
    """阶段一先固化提问契约，实际检索与流式回答在阶段二实现。"""
    knowledge_type = get_knowledge_type(req.knowledge_type)
    if not knowledge_type or not is_query_enabled(req.knowledge_type):
        return fail(
            f"{knowledge_type.label if knowledge_type else '该资料类型'}暂未启用查询",
            {"code": "knowledge_type_disabled", "knowledge_type": req.knowledge_type},
        )
    return fail(
        "公司制度问答正在建设中",
        {"code": "company_knowledge_not_ready", "knowledge_type": req.knowledge_type},
    )
