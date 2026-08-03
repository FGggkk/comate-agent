import json
import random
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.soul import SoulTemplate, UserSoul, UserSoulInventory
from app.models.user import User

SOULS_DIR = Path(__file__).parent.parent.parent / "souls"

TEMPLATES_META = [
    # 仅保留经典款「温柔陪伴型」作为注册默认灵魂，其余由管理端注入
    {"slug": "warm_companion", "name": "温柔陪伴型", "warmth": 0.90, "directness": 0.35},
]

ORB_META = {
    "warm_companion": {
        "tone": "温和、耐心",
        "intro": "先接住情绪，再慢慢陪你理清楚。",
        "colors": ["#FFD8B8", "#FFB088"],
        "expression": "smile",
    },
    "rational_clear": {
        "tone": "清醒、理性",
        "intro": "把问题拆开看，用结构感陪你稳住。",
        "colors": ["#B8D4F0", "#5FB0E8"],
        "expression": "calm",
    },
    "direct_coach": {
        "tone": "直接、行动",
        "intro": "少绕弯，帮你把下一步推起来。",
        "colors": ["#FFD0A8", "#FF9F45"],
        "expression": "firm",
    },
    "energetic_peer": {
        "tone": "轻快、有活力",
        "intro": "像身边的同伴，把日常聊得更松一点。",
        "colors": ["#A8E6CF", "#5FBE63"],
        "expression": "wink",
    },
    "patient_mentor": {
        "tone": "耐心、讲解",
        "intro": "一步一步陪你复盘、学习和成长。",
        "colors": ["#D4B8F0", "#9B6FD8"],
        "expression": "mentor",
    },
}


async def seed_templates(db: AsyncSession) -> list[SoulTemplate]:
    """初始化时写入模板到数据库"""
    result = await db.execute(select(SoulTemplate))
    existing = result.scalars().all()
    if existing:
        return existing

    templates = []
    for meta in TEMPLATES_META:
        md_path = SOULS_DIR / f"{meta['slug']}.md"
        soul_md = ""
        if md_path.exists():
            soul_md = md_path.read_text(encoding="utf-8")

        tmpl = SoulTemplate(
            slug=meta["slug"],
            name=meta["name"],
            description="",
            dimensions={
                "warmth": meta["warmth"],
                "directness": meta["directness"],
            },
            soul_markdown=soul_md,
        )
        db.add(tmpl)
        templates.append(tmpl)

    await db.commit()
    for t in templates:
        await db.refresh(t)
    return templates


async def get_templates(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SoulTemplate).where(SoulTemplate.status == "active"))
    templates = result.scalars().all()
    return [_template_to_dict(t) for t in templates]


async def grant_default_soul(user_id: str, db: AsyncSession) -> dict:
    """新用户 / 无灵魂用户默认拥有并注入经典款「温柔陪伴型」"""
    await seed_templates(db)
    tmpl = (
        await db.execute(select(SoulTemplate).where(SoulTemplate.slug == "warm_companion"))
    ).scalar_one_or_none()
    if not tmpl:
        return {"success": False, "message": "经典灵魂未初始化"}
    if tmpl.status != "active":
        tmpl.status = "active"

    # 已注入（active user_soul）则只确保卡槽有记录
    existing = await _active_user_soul(user_id, db)
    if existing:
        await _ensure_inventory_item(user_id, tmpl.id, db, source="default")
        await db.commit()
        return {"success": True, "already": True}

    db.add(UserSoul(user_id=user_id, template_id=tmpl.id, version_no=1, soul_markdown=tmpl.soul_markdown))
    await _ensure_inventory_item(user_id, tmpl.id, db, source="default")
    await db.commit()
    return {"success": True, "already": False}


def _template_to_dict(t: SoulTemplate, owned: bool = False, active: bool = False, acquired_at=None) -> dict:
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "description": t.description,
        "dimensions": t.dimensions,
        "soul_markdown": t.soul_markdown,
        "status": t.status,
        "orb": ORB_META.get(t.slug, {}),
        "color": t.color,
        "card_image": t.card_image,
        "avatar_image": t.avatar_image,
        "owned": owned,
        "active": active,
        "acquired_at": acquired_at.isoformat() if acquired_at else None,
    }


async def _active_user_soul(user_id: str, db: AsyncSession) -> UserSoul | None:
    result = await db.execute(
        select(UserSoul).where(
            UserSoul.user_id == user_id,
            UserSoul.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _ensure_inventory_item(user_id: str, template_id: str, db: AsyncSession, source: str = "draw") -> UserSoulInventory:
    result = await db.execute(
        select(UserSoulInventory).where(
            UserSoulInventory.user_id == user_id,
            UserSoulInventory.template_id == template_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        if item.status != "owned":
            item.status = "owned"
        return item

    item = UserSoulInventory(
        user_id=user_id,
        template_id=template_id,
        source=source,
        status="owned",
    )
    db.add(item)
    return item


async def get_inventory(user_id: str, db: AsyncSession) -> dict:
    await seed_templates(db)

    # 兜底：完全没有注入灵魂的用户（新注册 / 老用户空卡槽）默认拥有经典款
    if not await _active_user_soul(user_id, db):
        await grant_default_soul(user_id, db)

    # 用户卡槽上限（默认 6）
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    slot_capacity = user.slot_capacity if user else 6

    templates_result = await db.execute(select(SoulTemplate).where(SoulTemplate.status == "active"))
    templates = templates_result.scalars().all()

    active_soul = await _active_user_soul(user_id, db)
    active_template_id = str(active_soul.template_id) if active_soul and active_soul.template_id else None

    inventory_result = await db.execute(
        select(UserSoulInventory).where(
            UserSoulInventory.user_id == user_id,
            UserSoulInventory.status == "owned",
        )
    )
    inventory = inventory_result.scalars().all()

    # 补充「用户已拥有但已下架」的模板：保证卡槽数量与后端判断一致，且下架卡在卡槽可见可删
    if inventory:
        extra_result = await db.execute(
            select(SoulTemplate).where(SoulTemplate.id.in_([item.template_id for item in inventory]))
        )
        known_ids = {t.id for t in templates}
        for t in extra_result.scalars().all():
            if t.id not in known_ids:
                templates.append(t)

    order = {meta["slug"]: idx for idx, meta in enumerate(TEMPLATES_META)}
    templates.sort(key=lambda t: order.get(t.slug, 99))

    # 兼容旧数据：当前注入的灵魂若不在库存且卡槽未满，补入（卡槽满则不补，避免超限）
    if active_template_id and not any(str(item.template_id) == active_template_id for item in inventory):
        if len(inventory) < slot_capacity:
            await _ensure_inventory_item(user_id, active_template_id, db, source="default")
            await db.commit()
            inventory_result = await db.execute(
                select(UserSoulInventory).where(
                    UserSoulInventory.user_id == user_id,
                    UserSoulInventory.status == "owned",
                )
            )
            inventory = inventory_result.scalars().all()

    owned_by_template = {str(item.template_id): item for item in inventory}

    items = [
        _template_to_dict(
            t,
            owned=str(t.id) in owned_by_template,
            active=str(t.id) == active_template_id,
            acquired_at=owned_by_template[str(t.id)].acquired_at if str(t.id) in owned_by_template else None,
        )
        for t in templates
    ]
    # 卡槽内卡片补 slot_id（供删除 / 替换）
    for it in items:
        if it["owned"]:
            it["slot_id"] = str(owned_by_template[it["id"]].id)
    current = next((item for item in items if item["active"]), None)

    return {
        "templates": items,
        "current": current,
        "owned_count": sum(1 for item in items if item["owned"]),
        "total_count": len(items),
        "slot_capacity": slot_capacity,
        "occupied_count": sum(1 for item in items if item["owned"]),
        "has_unowned": any(not item["owned"] for item in items),
    }


async def draw_soul(user_id: str, db: AsyncSession) -> dict:
    """候选制抽卡：从管理端注入的（active）未收藏灵魂中随机返回一张，不写入卡槽"""
    await seed_templates(db)
    inventory = await get_inventory(user_id, db)
    available = [item for item in inventory["templates"] if not item["owned"]]

    if not available:
        return {
            "success": False,
            "message": "所有灵魂都已收入卡槽",
            "inventory": inventory,
        }

    picked = random.choice(available)
    return {
        "success": True,
        "message": "抽取成功",
        "template": picked,
        "inventory": inventory,
    }


async def save_soul_to_slot(user_id: str, template_id: str, replace_slot_id: str | None, db: AsyncSession) -> dict:
    """把抽到的灵魂保存进卡槽；卡槽满时必须传 replace_slot_id 替换一张旧卡"""
    tmpl = (await db.execute(select(SoulTemplate).where(SoulTemplate.id == template_id))).scalar_one_or_none()
    if not tmpl or tmpl.status != "active":
        return {"success": False, "message": "灵魂不存在或已下架"}

    existing = (await db.execute(
        select(UserSoulInventory).where(
            UserSoulInventory.user_id == user_id,
            UserSoulInventory.template_id == template_id,
            UserSoulInventory.status == "owned",
        )
    )).scalar_one_or_none()
    if existing:
        return {"success": False, "message": "该灵魂已在卡槽中"}

    user = (await db.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one_or_none()
    capacity = user.slot_capacity if user else 4

    owned_rows = (await db.execute(
        select(UserSoulInventory).where(
            UserSoulInventory.user_id == user_id,
            UserSoulInventory.status == "owned",
        )
    )).scalars().all()

    if len(owned_rows) >= capacity:
        # 卡槽已满：必须替换一张旧卡
        if not replace_slot_id:
            return {"success": False, "message": "卡槽已满，请选择一张旧灵魂替换", "need_replace": True}
        target = next((r for r in owned_rows if str(r.id) == replace_slot_id), None)
        if not target:
            return {"success": False, "message": "要替换的灵魂不在卡槽中"}

        active_soul = await _active_user_soul(user_id, db)
        replaced_active = bool(active_soul and active_soul.template_id and str(active_soul.template_id) == str(target.template_id))

        await db.delete(target)
        new_item = UserSoulInventory(user_id=user_id, template_id=tmpl.id, source="draw", status="owned")
        db.add(new_item)

        if replaced_active:
            # 被替换的是注入中的灵魂 → 新灵魂自动注入
            if active_soul:
                active_soul.status = "superseded"
            user_soul = UserSoul(user_id=user_id, template_id=tmpl.id, version_no=1, soul_markdown=tmpl.soul_markdown)
            db.add(user_soul)
        await db.commit()
        return {
            "success": True,
            "message": "已替换并保存" + ("，且自动注入新灵魂" if replaced_active else ""),
            "inventory": await get_inventory(user_id, db),
        }

    # 卡槽未满：直接保存
    db.add(UserSoulInventory(user_id=user_id, template_id=tmpl.id, source="draw", status="owned"))
    await db.commit()
    return {"success": True, "message": "已保存到卡槽", "inventory": await get_inventory(user_id, db)}


async def delete_soul_from_slot(user_id: str, slot_id: str, db: AsyncSession) -> dict:
    """从卡槽删除灵魂；删除注入中的灵魂时自动注入剩余的一张或置空"""
    item = (await db.execute(
        select(UserSoulInventory).where(
            UserSoulInventory.id == slot_id,
            UserSoulInventory.user_id == user_id,
            UserSoulInventory.status == "owned",
        )
    )).scalar_one_or_none()
    if not item:
        return {"success": False, "message": "卡槽中的灵魂不存在"}

    active_soul = await _active_user_soul(user_id, db)
    deleting_active = bool(active_soul and active_soul.template_id and str(active_soul.template_id) == str(item.template_id))

    await db.delete(item)

    if deleting_active and active_soul:
        active_soul.status = "superseded"
        remaining = (await db.execute(
            select(UserSoulInventory).where(
                UserSoulInventory.user_id == user_id,
                UserSoulInventory.status == "owned",
            ).order_by(UserSoulInventory.acquired_at)
        )).scalars().all()
        # 自动注入剩余第一张「仍上架」的灵魂，避免注入已下架（用户不可见）模板
        next_target = None
        for r in remaining:
            t2 = (await db.execute(
                select(SoulTemplate).where(SoulTemplate.id == r.template_id, SoulTemplate.status == "active")
            )).scalar_one_or_none()
            if t2:
                next_target = t2
                break
        if next_target:
            db.add(UserSoul(user_id=user_id, template_id=next_target.id, version_no=1, soul_markdown=next_target.soul_markdown))

    await db.commit()
    return {"success": True, "message": "已从卡槽删除", "inventory": await get_inventory(user_id, db)}


async def inject_soul(user_id: str, template_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(UserSoulInventory).where(
            UserSoulInventory.user_id == user_id,
            UserSoulInventory.template_id == template_id,
            UserSoulInventory.status == "owned",
        )
    )
    if not result.scalar_one_or_none():
        return {"success": False, "message": "请先抽到这个人设"}

    result = await confirm_soul(user_id, template_id, db)
    if not result.get("success"):
        return result

    return {
        "success": True,
        "message": "已切换当前风格",
        "inventory": await get_inventory(user_id, db),
    }


def recommend(answers: list[dict]) -> list[dict]:
    """简单的规则推荐"""
    warmth_score = 0.0
    directness_score = 0.0
    count = 0
    for a in answers:
        if a.get("dimension") == "warmth":
            warmth_score += a.get("value", 0.5)
            count += 1
        elif a.get("dimension") == "directness":
            directness_score += a.get("value", 0.5)
            count += 1

    if count > 0:
        warmth_score /= count
        directness_score /= count
    else:
        warmth_score = 0.5
        directness_score = 0.5

    scored = []
    for meta in TEMPLATES_META:
        score = 1.0 - abs(meta["warmth"] - warmth_score) * 0.5 - abs(meta["directness"] - directness_score) * 0.5
        scored.append({"slug": meta["slug"], "name": meta["name"], "score": round(score, 2)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:2]


async def preview(slug: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SoulTemplate).where(SoulTemplate.slug == slug))
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        return []

    # 返回模板的固定预览问题
    return [
        {"role": "user", "content": "你好呀，今天心情不太好。"},
        {"role": "assistant", "content": preview_reply(slug, "greeting")},
        {"role": "user", "content": "你觉得我应该怎么调整一下状态？"},
        {"role": "assistant", "content": preview_reply(slug, "advice")},
    ]


def preview_reply(slug: str, topic: str) -> str:
    replies = {
        "warm_companion": {
            "greeting": "嗯，我在这里呢。心情不好的时候不用勉强自己开心，想聊聊发生了什么，还是想安静一会儿？我都陪着你。",
            "advice": "先别急着想「应该怎么做」。有时候允许自己停下来喘口气，反而能看清方向。要不要一起泡杯热的东西，然后慢慢理一理？",
        },
        "rational_clear": {
            "greeting": "收到。情绪波动是正常的。能具体说说发生了什么吗？我们理性分析一下，看看问题出在哪里。",
            "advice": "建议先把问题拆解成可控的小块。你现在面临的具体困难是什么？目标是什么？我们来列个清单。",
        },
        "direct_coach": {
            "greeting": "别闷着。状态不好很正常，但不行动状态不会自己好。先告诉我发生了什么，然后我们一起制定一个计划。",
            "advice": "我的建议很简单：先做一件小事。5 分钟内能完成的那种。完成之后你会发现状态已经开始变化了。试试？",
        },
        "energetic_peer": {
            "greeting": "哎呀，不开心吗？来来来，先给你一个虚拟抱抱 🤗 不管发生了什么，有我在呢！想吐槽还是想听个段子？",
            "advice": "我有个主意！先做一件让你开心的小事——听首喜欢的歌、吃个好吃的东西。状态好了之后我们再一起想办法！",
        },
        "patient_mentor": {
            "greeting": "每个人都有状态不好的时候，这很正常。我注意到你说「今天」，说明不是一直这样对吗？能跟我讲讲发生了什么吗？",
            "advice": "让我们一步步来。首先，确认一下现在最困扰你的具体问题是什么。然后我们一起分析原因、找到对策。每一步我都会陪你。",
        },
    }
    return replies.get(slug, {}).get(topic, "让我想想……")


async def confirm_soul(user_id: str, template_id: str, db: AsyncSession) -> dict:
    result = await db.execute(select(SoulTemplate).where(SoulTemplate.id == template_id))
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        return {"success": False, "message": "模板不存在"}

    # 将之前 active 的设为 superseded
    result = await db.execute(
        select(UserSoul).where(
            UserSoul.user_id == user_id,
            UserSoul.status == "active",
        )
    )
    old = result.scalar_one_or_none()
    if old:
        old.status = "superseded"

    user_soul = UserSoul(
        user_id=user_id,
        template_id=template_id,
        version_no=1,
        soul_markdown=tmpl.soul_markdown,
    )
    db.add(user_soul)
    await _ensure_inventory_item(user_id, template_id, db, source="default")

    # 更新用户 onboarding 状态
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user and user.onboarding_status == "none":
        user.onboarding_status = "completed"

    await db.commit()
    await db.refresh(user_soul)

    return {"success": True, "soul_id": str(user_soul.id)}
