"""购物推荐服务 — 异步搜索 + LLM 整理方案"""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.tools import TOOL_REGISTRY
from app.services.model_gateway import gateway


# 用 SSE 存储进度状态（生产环境应换 Redis）
_progress_store: dict[str, dict] = {}


def _get_progress(task_id: str) -> dict:
    if task_id not in _progress_store:
        _progress_store[task_id] = {
            "status": "pending",
            "parts": [],
            "results": [],
            "current": 0,
            "total": 0,
            "message": "",
            "plans": None,
            "analyzed_items": None,
        }
    return _progress_store[task_id]


async def run_pipeline(demand: str, task_id: str, user_id: str = ""):
    """后台流水线：分析需求 → 逐个搜索 → 整理方案"""
    try:
        progress = _get_progress(task_id)
        progress["status"] = "analyzing"
        progress["message"] = "正在分析需求..."

        # 1. 分析需求
        items = await analyze_demand(demand)
        if not items:
            progress["status"] = "error"
            progress["message"] = "需求分析失败"
            return

        progress["analyzed_items"] = items
        progress["status"] = "searching"
        progress["total"] = len(items)
        progress["parts"] = items

        # 2. 逐个搜索
        progress["phase"] = "searching"
        search_tool = TOOL_REGISTRY.get("search_web")
        for i, item in enumerate(items):
            progress["current"] = i
            progress["message"] = f"正在搜索 {item['name']}..."

            if search_tool:
                result_text = await search_tool.execute(query=item.get("keywords", item["name"]))
            else:
                result_text = "搜索工具不可用"

            progress["results"].append({
                "name": item["name"],
                "raw": result_text,
                "status": "done",
            })

        # 3. 整理方案
        progress["phase"] = "building"
        progress["status"] = "building"
        progress["message"] = "正在分析搜索结果、生成方案..."
        event = await build_plans(demand, progress["results"], task_id)

        if event["type"] == "complete":
            progress["status"] = "done"
            progress["plans"] = event["data"]
            progress["message"] = "方案已生成"
            # 自动保存到数据库
            if user_id:
                try:
                    from app.db.session import async_session_factory
                    async with async_session_factory() as db:
                        await auto_save_plan(task_id, user_id, db)
                except Exception as e:
                    print(f"[shopping] 自动保存失败: {e}")
        else:
            progress["status"] = "error"
            progress["message"] = "方案生成失败"

    except Exception as e:
        p = _get_progress(task_id)
        p["status"] = "error"
        p["message"] = str(e)


def get_progress(task_id: str) -> dict | None:
    return _progress_store.get(task_id)


async def analyze_demand(demand: str) -> list[dict] | None:
    """用 LLM 分析用户需求，返回需要搜索的商品列表"""
    prompt = f"""你是一个购物顾问。用户说：{demand}

请分析用户的购物需求，推荐具体的商品型号并生成搜索关键词。

规则：
1. 【单件商品】如果是手机/衣服/家电等，推荐 2-3 个具体型号/款式，每个单独列一条
2. 【电脑配置】如果是配电脑，列出 CPU、GPU、内存、硬盘、电源、主板、机箱等每个配件
3. keywords 要带品牌型号 + "京东" + "价格"，确保能搜到具体商品页

示例：
用户说"3000元拍照好的手机"
→ [{{"name":"小米Civi 4 Pro","keywords":"小米Civi 4 Pro 京东 价格"}},{{"name":"vivo S20","keywords":"vivo S20 京东 价格"}},{{"name":"荣耀300","keywords":"荣耀300 京东 价格"}}]

用户说"5000元配电脑打游戏"
→ [{{"name":"i5-13400F","keywords":"i5-13400F 京东 价格"}},{{"name":"RTX 4060","keywords":"RTX 4060 京东 价格"}},{{"name":"16G DDR5 内存","keywords":"16G DDR5 内存 京东 价格"}}]

只返回 JSON 数组，不要其他文字。"""
    try:
        resp_text = await gateway.chat(prompt)
        # 提取 JSON
        resp_text = resp_text.strip()
        if resp_text.startswith("```"):
            resp_text = resp_text.split("\n", 1)[1]
            resp_text = resp_text.rsplit("```", 1)[0]
        items = json.loads(resp_text.strip())
        return items if isinstance(items, list) else None
    except Exception as e:
        print(f"[shopping] 分析需求失败: {e}")
        return None


async def search_parts(items: list[dict], task_id: str):
    """逐个搜索商品，更新进度"""
    progress = _get_progress(task_id)
    progress["status"] = "searching"
    progress["total"] = len(items)
    progress["parts"] = items

    search_tool = TOOL_REGISTRY.get("search_web")

    for i, item in enumerate(items):
        progress["current"] = i
        progress["message"] = f"正在搜索 {item['name']}..."
        yield {"type": "searching", "data": item}

        if search_tool:
            result_text = await search_tool.execute(query=item.get("keywords", item["name"]))
        else:
            result_text = "搜索工具不可用"

        # 从结果中提取商品信息
        result = {
            "name": item["name"],
            "raw": result_text,
            "status": "done",
        }
        progress["results"].append(result)
        yield {"type": "found", "data": result}

    progress["current"] = len(items)
    progress["status"] = "building"


async def build_plans(demand: str, results: list[dict], task_id: str):
    """用 LLM 将搜索结果整理成方案"""
    search_summary = "\n\n".join(
        f"## {r['name']}\n{r.get('raw', '未搜索到结果')}" for r in results
    )

    prompt = f"""你是一个购物顾问。用户的需求是：{demand}

以下是搜索到的商品信息（包含标题、价格、来源链接）：
{search_summary}

请基于以上真实搜索结果，为用户整理出 2-3 套推荐方案。

【核心要求 — 每套方案必须有明显差异】
- 方案1（极致性价比）：总价最低，用最便宜但够用的配件
- 方案2（均衡主力）：性能与价格平衡，主流配置
- 方案3（品质优先）：预算内选最好的，不将就
- 如果预算很低，只出2套；如果预算充足，出3套

【约束 — 必须遵守】
1. 【禁止编造】只能使用上方搜索结果中出现的商品和价格
2. 【价格必须明确】搜到的用具体数字，没搜到的标"未搜索到该商品价格"，不要写"以实际为准"
3. 【链接优先选商品页】如果搜索结果中有 item.jd.com 等商品详情链接，优先使用；没有才用其他链接
4. 【总价计算】每个方案的 total 必须等于所有 parts price 之和

返回 JSON 格式：
{{
  "summary": "一句话总结（包含3套方案的不同定位）",
  "plans": [
    {{
      "name": "极致性价比版",
      "total": 总价(数字),
      "desc": "方案说明（说明为什么这套方案适合什么用户）",
      "parts": [
        {{"name": "商品名", "price": 价格(数字), "url": "真实链接", "shop": "平台", "note": "亮点说明"}}
      ]
    }}
  ]
}}

只返回 JSON，不要其他文字。"""

    progress = _get_progress(task_id)
    progress["message"] = "正在生成方案..."

    try:
        resp_text = await gateway.chat(prompt)
        resp_text = resp_text.strip()
        if resp_text.startswith("```"):
            resp_text = resp_text.split("\n", 1)[1]
            resp_text = resp_text.rsplit("```", 1)[0]
        plans = json.loads(resp_text.strip())

        progress["status"] = "done"
        progress["plans"] = plans
        progress["message"] = "方案已生成"
        return {"type": "complete", "data": plans}
    except Exception as e:
        progress["status"] = "error"
        progress["message"] = f"生成方案失败: {e}"
        return {"type": "error", "data": {"message": str(e)}}


async def save_plans(user_id: str, demand: str, plans: dict, db: AsyncSession):
    """保存方案到数据库"""
    from app.models.shopping import ShoppingPlan

    plan = ShoppingPlan(user_id=user_id, demand=demand, plans=plans)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return str(plan.id)


async def auto_save_plan(task_id: str, user_id: str, db: AsyncSession):
    """自动保存已完成的方案"""
    progress = _progress_store.get(task_id)
    if not progress or not progress.get('plans'):
        return None
    plan_id = await save_plans(user_id, progress['demand'], progress['plans'], db)
    progress['saved_plan_id'] = plan_id
    return plan_id


async def toggle_favorite(plan_id: str, user_id: str, db: AsyncSession):
    """切换收藏状态"""
    from sqlalchemy import select, update
    from app.models.shopping import ShoppingPlan

    result = await db.execute(
        select(ShoppingPlan).where(ShoppingPlan.id == plan_id, ShoppingPlan.user_id == user_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return False
    new_val = 'false' if plan.favorited == 'true' else 'true'
    await db.execute(
        update(ShoppingPlan).where(ShoppingPlan.id == plan_id).values(favorited=new_val)
    )
    await db.commit()
    return new_val == 'true'


async def delete_plan(plan_id: str, user_id: str, db: AsyncSession):
    """删除方案"""
    from sqlalchemy import delete as sa_delete
    from app.models.shopping import ShoppingPlan

    await db.execute(
        sa_delete(ShoppingPlan).where(ShoppingPlan.id == plan_id, ShoppingPlan.user_id == user_id)
    )
    await db.commit()
    return True


async def get_history(user_id: str, db: AsyncSession) -> list[dict]:
    """获取用户的历史方案"""
    from app.models.shopping import ShoppingPlan

    result = await db.execute(
        select(ShoppingPlan)
        .where(ShoppingPlan.user_id == user_id)
        .order_by(ShoppingPlan.created_at.desc())
        .limit(20)
    )
    plans = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "demand": p.demand,
            "plans": p.plans,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in plans
    ]


async def get_plan_detail(plan_id: str, user_id: str, db: AsyncSession) -> dict | None:
    """获取单个方案详情"""
    from app.models.shopping import ShoppingPlan

    result = await db.execute(
        select(ShoppingPlan).where(
            ShoppingPlan.id == plan_id, ShoppingPlan.user_id == user_id
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    return {
        "id": str(plan.id),
        "demand": plan.demand,
        "plans": plan.plans,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }
