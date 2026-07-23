import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.soul import SoulTemplate, UserSoul

SOULS_DIR = Path(__file__).parent.parent.parent / "souls"

TEMPLATES_META = [
    {"slug": "warm_companion", "name": "温柔陪伴型", "warmth": 0.90, "directness": 0.35},
    {"slug": "rational_clear", "name": "理性清醒型", "warmth": 0.35, "directness": 0.80},
    {"slug": "direct_coach", "name": "直率督促型", "warmth": 0.40, "directness": 0.90},
    {"slug": "energetic_peer", "name": "活力同伴型", "warmth": 0.80, "directness": 0.55},
    {"slug": "patient_mentor", "name": "耐心导师型", "warmth": 0.75, "directness": 0.50},
]


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
    return [
        {
            "id": str(t.id),
            "slug": t.slug,
            "name": t.name,
            "description": t.description,
            "dimensions": t.dimensions,
        }
        for t in templates
    ]


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

    # 更新用户 onboarding 状态
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user and user.onboarding_status == "none":
        user.onboarding_status = "completed"

    await db.commit()
    await db.refresh(user_soul)

    return {"success": True, "soul_id": str(user_soul.id)}
