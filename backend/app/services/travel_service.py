import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.travel import TravelDay, TravelPlan


async def ai_generate(data: dict, db: AsyncSession) -> dict:
    from app.services.model_gateway import gateway

    days = data["days"]
    prefs = "、".join(data.get("preferences", [])) or "无特殊偏好"
    note = data.get("note", "") or "无"
    start = data["start_date"]

    prompt = f"""你是一个旅游规划专家。根据以下信息制定详细行程：

目的地：{data['destination']}
天数：{days}天
总预算：{data.get('budget', 0) // 100}元（这是总预算，所有天数每项活动的花费之和必须严格在此预算之内）
人数：{data.get('adults', 1)}成人，{data.get('children', 0)}儿童
偏好：{prefs}
出发日期：{start}
备注：{note}

【预算规则——必须严格遵守】
- 总预算为 {data.get('budget', 0) // 100} 元，所有天数所有活动的 cost 加总不得超过此金额
- 如果预算有限，选择更经济的活动、减少高消费项目、缩短部分活动时长
- 不允许超出预算后虚报价格，必须按真实市场价格填写 cost
- 如果预算不足以覆盖所有天数，优先保证住宿和基础交通，其他活动从简

要求：
1. 每天分上午(morning)、下午(afternoon)、晚上(evening)三个时段
2. 每项活动包含 title(标题)、description(描述)、cost(预估费用元)、duration(建议时长)、tips(小贴士)
3. 按天输出 JSON
4. 最后输出 budget_detail 对象(accommodation住宿/food餐饮/tickets门票/transport交通/other其他)

只输出 JSON，不要多余文字。格式：
{{
  "title": "北京3日游",
  "days": [
    {{
      "day_number": 1,
      "date": "{start}",
      "segments": [
        {{"period": "morning", "title": "故宫博物院", "description": "...", "cost": 60, "duration": "2h", "tips": "提前预约"}},
        {{"period": "afternoon", "title": "...", "description": "...", "cost": 0, "duration": "1h", "tips": ""}},
        {{"period": "evening", "title": "...", "description": "...", "cost": 80, "duration": "1.5h", "tips": ""}}
      ],
      "total_cost": 140
    }}
  ],
  "budget_detail": {{"accommodation": 1800, "food": 1200, "tickets": 800, "transport": 600, "other": 600}}
}}"""

    full = ""
    async for chunk in gateway.stream(prompt):
        full += chunk
    full = full.strip().strip("```json").strip("```").strip()
    try:
        result = json.loads(full)
    except json.JSONDecodeError:
        # 尝试修复常见JSON问题
        import re
        fixed = re.sub(r',\s*}', '}', full)  # 去掉尾逗号
        fixed = re.sub(r',\s*]', ']', fixed)
        try:
            result = json.loads(fixed)
        except json.JSONDecodeError:
            print(f"[travel] AI JSON parse failed: {full[:200]}")
            return {"error": "AI 生成失败，请重试"}

    # 校验 JSON 结构
    if not isinstance(result.get("days"), list) or not result["days"]:
        print(f"[travel] AI output missing valid days array: {json.dumps(result, ensure_ascii=False)[:200]}")
        return {"error": "AI 生成失败，请重试"}

    # 预算校验：超预算则让 AI 重新规划（不强行压缩价格）
    budget_yuan = data.get("budget", 0) / 100  # 转为元
    max_budget = budget_yuan * 1.1  # 允许10%浮动
    all_segments = []
    for day_data in result.get("days", []):
        for seg in day_data.get("segments", []):
            all_segments.append(seg)
    total_cost = sum(s.get("cost", 0) for s in all_segments)

    if budget_yuan > 0 and total_cost > max_budget:
        # 让 AI 重新规划，告诉它之前超预算了
        retry_prompt = f"""你之前规划的行程总花费为 {total_cost} 元，超出预算 {budget_yuan} 元。
请重新规划，严格控制所有活动花费总和不超过 {budget_yuan} 元。

之前的规划（供参考，需要调整价格）：
{json.dumps(result, ensure_ascii=False, indent=2)[:1500]}

要求：
- 总花费不得超过 {budget_yuan} 元
- 选择更经济的活动方案，减少高消费项目
- 天数、目的地不变
- 保持合理的行程质量，每天仍有 morning/afternoon/evening 三段时间安排
- 格式与之前完全一致，只输出 JSON"""

        full = ""
        async for chunk in gateway.stream(retry_prompt):
            full += chunk
        full = full.strip().strip("```json").strip("```").strip()
        try:
            retry_result = json.loads(full)
        except json.JSONDecodeError:
            import re
            fixed = re.sub(r',\s*}', '}', full)
            fixed = re.sub(r',\s*]', ']', fixed)
            try:
                retry_result = json.loads(fixed)
            except json.JSONDecodeError:
                retry_result = result  # 重试失败，使用原结果

        # 校验重试结果
        if isinstance(retry_result.get("days"), list) and retry_result["days"]:
            retry_segments = []
            for day_data in retry_result["days"]:
                for seg in day_data.get("segments", []):
                    retry_segments.append(seg)
            retry_total = sum(s.get("cost", 0) for s in retry_segments)
            if retry_total < total_cost:  # 重试有改善
                result = retry_result
                total_cost = retry_total

    # 保存到数据库
    plan = TravelPlan(
        user_id=data["user_id"],
        title=result.get("title", f"{data['destination']}{days}日游"),
        destination=data["destination"],
        start_date=datetime.strptime(str(start), "%Y-%m-%d").date(),
        days=days,
        budget=data.get("budget", 0),
        adults=data.get("adults", 1),
        children=data.get("children", 0),
        preferences=data.get("preferences", []),
        note=data.get("note", ""),
        budget_detail=result.get("budget_detail", {}),
    )
    db.add(plan)
    await db.flush()

    for day_data in result.get("days", []):
        day_date = datetime.strptime(str(start), "%Y-%m-%d").date() + timedelta(days=day_data["day_number"] - 1)
        day = TravelDay(
            plan_id=plan.id,
            day_number=day_data["day_number"],
            date=day_date,
            segments=day_data.get("segments", []),
            total_cost=day_data.get("total_cost", 0),
        )
        db.add(day)

    await db.commit()
    await db.refresh(plan)
    return await _plan_to_dict(plan, db)


async def get_plans(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(TravelPlan).where(TravelPlan.user_id == user_id).order_by(TravelPlan.updated_at.desc()).limit(20)
    )
    plans = []
    for p in result.scalars().all():
        days_result = await db.execute(select(TravelDay).where(TravelDay.plan_id == p.id).order_by(TravelDay.day_number))
        days = [_day_to_dict(d) for d in days_result.scalars().all()]
        plans.append({**_plan_brief(p), "days": days})
    return plans


async def get_plan(plan_id: str, user_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(select(TravelPlan).where(TravelPlan.id == plan_id, TravelPlan.user_id == user_id))
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    return await _plan_to_dict(plan, db)


async def update_plan(plan_id: str, user_id: str, data: dict, db: AsyncSession) -> dict | None:
    result = await db.execute(select(TravelPlan).where(TravelPlan.id == plan_id, TravelPlan.user_id == user_id))
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    for key in ("title", "saved"):
        if key in data:
            setattr(plan, key, data[key])
    plan.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _plan_to_dict(plan, db)


async def delete_plan(plan_id: str, user_id: str, db: AsyncSession) -> bool:
    result = await db.execute(select(TravelPlan).where(TravelPlan.id == plan_id, TravelPlan.user_id == user_id))
    plan = result.scalar_one_or_none()
    if not plan:
        return False
    await db.delete(plan)
    await db.commit()
    return True


async def regenerate_day(plan_id: str, user_id: str, day_number: int, db: AsyncSession) -> dict | None:
    from app.services.model_gateway import gateway

    result = await db.execute(select(TravelPlan).where(TravelPlan.id == plan_id, TravelPlan.user_id == user_id))
    plan = result.scalar_one_or_none()
    if not plan:
        return None

    prompt = f"""我是旅游规划助手。重新规划以下行程的第{day_number}天：

目的地：{plan.destination}
总天数：{plan.days}天
预算：{plan.budget}元
偏好：{'、'.join(plan.preferences or [])}

只输出第{day_number}天的行程，格式同之前（morning/afternoon/evening三段）。
只输出 JSON 数组：
[{{"period": "morning", "title": "...", "description": "...", "cost": 0, "duration": "1h", "tips": ""}}]"""

    full = ""
    async for chunk in gateway.stream(prompt):
        full += chunk
    full = full.strip().strip("```json").strip("```").strip()
    try:
        segments = json.loads(full)
    except json.JSONDecodeError:
        return None

    day_result = await db.execute(
        select(TravelDay).where(TravelDay.plan_id == plan_id, TravelDay.day_number == day_number)
    )
    day = day_result.scalar_one_or_none()
    if not day:
        day_date = plan.start_date + timedelta(days=day_number - 1)
        day = TravelDay(plan_id=plan.id, day_number=day_number, date=day_date, segments=segments)
        db.add(day)
    else:
        day.segments = segments
    day.total_cost = sum(s.get("cost", 0) for s in segments)
    await db.commit()
    return _day_to_dict(day)


def _plan_brief(p: TravelPlan) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "destination": p.destination,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "days": p.days,
        "budget": p.budget,
        "adults": p.adults,
        "children": p.children,
        "preferences": p.preferences or [],
        "note": p.note or "",
        "saved": p.saved,
        "budget_detail": p.budget_detail or {},
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


async def _plan_to_dict(p: TravelPlan, db: AsyncSession) -> dict:
    result = await db.execute(select(TravelDay).where(TravelDay.plan_id == p.id).order_by(TravelDay.day_number))
    days = [_day_to_dict(d) for d in result.scalars().all()]
    return {**_plan_brief(p), "days": days}


def _day_to_dict(d: TravelDay) -> dict:
    return {
        "id": str(d.id),
        "day_number": d.day_number,
        "date": d.date.isoformat() if d.date else None,
        "segments": d.segments or [],
        "total_cost": d.total_cost,
    }
