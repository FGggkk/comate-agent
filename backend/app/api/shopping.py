"""购物计划 API — 需求分析 + 异步搜索 + SSE 进度 + 方案管理"""

import asyncio
import json
import uuid as _uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok, fail
from app.db.session import get_db
from app.services import shopping_service

router = APIRouter(prefix="/api/shopping", tags=["shopping"])

# 持有后台任务引用，防止 GC 回收
_background_tasks: dict[str, asyncio.Task] = {}


class GenerateRequest(BaseModel):
    demand: str


@router.post("/generate")
async def api_generate(
    req: GenerateRequest,
    user_id: str = Depends(get_current_user),
):
    """开始生成购物方案（后台异步执行，不依赖 SSE 连接）"""
    task_id = f"shopping_{_uuid.uuid4().hex[:12]}"

    # 初始化进度
    progress = shopping_service._get_progress(task_id)
    progress["status"] = "analyzing"
    progress["message"] = "正在分析需求..."
    progress["demand"] = req.demand

    # 启动后台任务（独立于 SSE 连接运行）
    task = asyncio.create_task(shopping_service.run_pipeline(req.demand, task_id, user_id))
    _background_tasks[task_id] = task
    task.add_done_callback(lambda t: _background_tasks.pop(task_id, None))

    return ok({"task_id": task_id, "demand": req.demand})


@router.get("/progress/{task_id}")
async def api_progress(task_id: str):
    """SSE 推送搜索进度（只读，不执行搜索）"""
    progress = shopping_service.get_progress(task_id)
    if not progress:
        return fail("任务不存在")

    async def event_stream():
        # 持续轮询直到任务完成或出错
        last_result_count = 0
        items_pushed = False

        while True:
            p = shopping_service.get_progress(task_id)
            if not p:
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': '任务已过期'}}, ensure_ascii=False)}\n\n"
                break

            # 推送 analyzed_items（配件列表）
            if p.get("analyzed_items") and not items_pushed:
                yield f"data: {json.dumps({'type': 'analyzed', 'data': {'items': p['analyzed_items']}}, ensure_ascii=False)}\n\n"
                items_pushed = True

            # 推送新增的搜索结果
            current_count = len(p.get("results", []))
            if current_count > last_result_count:
                for r in p["results"][last_result_count:]:
                    yield f"data: {json.dumps({'type': 'found', 'data': r}, ensure_ascii=False)}\n\n"
                last_result_count = current_count

            # 检查是否完成
            if p["status"] == "done":
                if p.get("plans"):
                    yield f"data: {json.dumps({'type': 'complete', 'data': p['plans']}, ensure_ascii=False)}\n\n"
                break
            elif p["status"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': p.get('message', '')}}, ensure_ascii=False)}\n\n"
                break
            else:
                # 推送状态
                yield f"data: {json.dumps({'type': 'status', 'data': {'status': p['status'], 'phase': p.get('phase', ''), 'message': p.get('message', '')}}, ensure_ascii=False)}\n\n"

            await asyncio.sleep(1)

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class SaveRequest(BaseModel):
    task_id: str


@router.post("/save")
async def api_save(
    req: SaveRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存已生成的方案到数据库"""
    progress = shopping_service.get_progress(req.task_id)
    if not progress or not progress.get("plans"):
        return fail("方案不存在或未完成")

    plan_id = await shopping_service.save_plans(
        user_id, progress["demand"], progress["plans"], db
    )
    return ok({"plan_id": plan_id})


@router.get("/history")
async def api_history(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取历史方案列表"""
    plans = await shopping_service.get_history(user_id, db)
    return ok(plans)


@router.get("/plan/{plan_id}")
async def api_plan_detail(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个方案详情"""
    plan = await shopping_service.get_plan_detail(plan_id, user_id, db)
    if not plan:
        return fail("方案不存在")
    return ok(plan)


@router.post("/plan/{plan_id}/favorite")
async def api_favorite(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换收藏状态"""
    result = await shopping_service.toggle_favorite(plan_id, user_id, db)
    return ok({"favorited": result})


@router.delete("/plan/{plan_id}")
async def api_delete_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除方案"""
    await shopping_service.delete_plan(plan_id, user_id, db)
    return ok(None, "已删除")
