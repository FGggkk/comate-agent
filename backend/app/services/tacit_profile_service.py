import asyncio
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.conversation import Message, Session
from app.models.memory import MemoryItem
from app.models.tacit import SessionSummary, TacitProfile, TacitProfileVersion
from app.plugins.company_knowledge.memory_boundary import profile_safe_messages
from app.services.memory_gate_service import append_gate_trace
from app.services.memory_service import classify_query_topics, is_forbidden_text


APP_TZ = timezone(timedelta(hours=8))
WINDOW_DAYS = 30
MAX_RECENT_SUMMARIES = 10
MIN_SUMMARIES_FOR_PROFILE = 2
HIGH_CONFIDENCE = 0.58
PROMPT_VERSION = "tacit-profile-v2"
MODEL_VERSION = "rules-v2"

DIMENSIONS = {
    "life_stage": "近期阶段",
    "long_term_goals": "长期目标",
    "routines": "行为习惯",
    "decision_style": "处事风格",
    "emotional_patterns": "情绪模式",
    "communication_style": "沟通偏好",
    "support_preferences": "陪伴策略",
}

DIMENSION_ORDER = [
    "life_stage",
    "long_term_goals",
    "routines",
    "decision_style",
    "emotional_patterns",
    "communication_style",
    "support_preferences",
]

ALWAYS_PERSONA_DIMENSIONS = {
    "decision_style",
    "emotional_patterns",
    "communication_style",
    "support_preferences",
}


def schedule_tacit_refresh(user_id: str, session_id: str) -> None:
    asyncio.create_task(refresh_tacit_profile_background(user_id, session_id))


async def refresh_tacit_profile_background(user_id: str, session_id: str) -> None:
    try:
        async with async_session_factory() as db:
            await refresh_after_conversation(user_id, session_id, db)
    except Exception as e:
        print(f"[tacit] 后台画像更新失败: {e}")


async def refresh_after_conversation(user_id: str, session_id: str, db: AsyncSession) -> dict:
    session_summary = await summarize_session(user_id, session_id, db)
    if not session_summary:
        return {"success": False, "message": "会话摘要不可用"}
    profile = await update_tacit_profile(user_id, db)
    return {"success": True, "summary_id": str(session_summary.id), "profile": profile}


async def summarize_session(user_id: str, session_id: str, db: AsyncSession) -> SessionSummary | None:
    session_result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        return None

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(120)
    )
    messages = result.scalars().all()
    if not any(m.role == "user" and (m.content or "").strip() for m in messages):
        return None

    persona_messages = profile_safe_messages(messages)
    if persona_messages:
        payload = await _summarize_messages(persona_messages)
    else:
        payload = {
            "summary": "本会话包含公司知识问答，未提取个人画像信息。",
            "topics": ["company_knowledge"],
            "signals": _empty_profile(),
        }
    started_at = messages[0].created_at if messages else session.created_at
    ended_at = messages[-1].created_at if messages else session.updated_at

    existing_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    item = existing_result.scalar_one_or_none()
    if not item:
        item = SessionSummary(user_id=user_id, session_id=session_id)
        db.add(item)

    item.summary = payload["summary"][:4000]
    item.topics = {"items": payload.get("topics", [])[:12]}
    item.signals = payload.get("signals", _empty_profile())
    item.message_count = len(messages)
    item.started_at = started_at
    item.ended_at = ended_at
    await db.commit()
    await db.refresh(item)
    return item


async def update_tacit_profile(user_id: str, db: AsyncSession) -> dict | None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=WINDOW_DAYS)
    result = await db.execute(
        select(SessionSummary)
        .where(
            SessionSummary.user_id == user_id,
            SessionSummary.ended_at.is_not(None),
            SessionSummary.ended_at >= window_start,
        )
        .order_by(SessionSummary.ended_at.desc())
        .limit(MAX_RECENT_SUMMARIES)
    )
    recent = list(reversed(result.scalars().all()))
    co_created_memories = await _load_co_created_memories(user_id, db, now)
    if len(recent) < MIN_SUMMARIES_FOR_PROFILE and not co_created_memories:
        return None

    profile_result = await db.execute(
        select(TacitProfile).where(TacitProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    base_profile = deepcopy(profile.profile if profile else _empty_profile())

    decayed_profile, decay_log = _apply_decay(base_profile, now)
    replacement_terms = _collect_replacement_terms(co_created_memories)
    decayed_profile, replacement_log = _apply_explicit_replacements(decayed_profile, replacement_terms, now)
    decay_log = _combine_profile_logs(decay_log, replacement_log)
    evidence = _collect_evidence(recent)
    co_created_evidence = _collect_co_created_evidence(co_created_memories, now)
    evidence = _combine_evidence(evidence, co_created_evidence)
    merged_profile, delta = _merge_profile(decayed_profile, evidence, now)
    summary = await _profile_summary(merged_profile)
    confidence = _profile_confidence(merged_profile)
    horizon_start = min((s.started_at or s.ended_at for s in recent if s.started_at or s.ended_at), default=window_start)
    horizon_end = max((s.ended_at or s.started_at for s in recent if s.started_at or s.ended_at), default=now)

    if not profile:
        profile = TacitProfile(user_id=user_id, version_no=0, profile=_empty_profile())
        db.add(profile)
        await db.flush()

    next_version = (profile.version_no or 0) + 1
    version = TacitProfileVersion(
        profile_id=profile.id,
        user_id=user_id,
        version_no=next_version,
        input_window_start=horizon_start,
        input_window_end=horizon_end,
        base_profile=base_profile,
        new_evidence=evidence,
        delta=delta,
        merged_profile=merged_profile,
        decay_applied=decay_log,
        model_version=MODEL_VERSION,
        prompt_version=PROMPT_VERSION,
    )
    db.add(version)

    profile.profile = merged_profile
    profile.summary = summary
    profile.version_no = next_version
    profile.confidence = confidence
    profile.horizon_start = horizon_start
    profile.horizon_end = horizon_end
    profile.last_analyzed_at = now
    profile.next_review_at = now + timedelta(days=7)
    profile.status = "active"
    await db.commit()
    await db.refresh(profile)
    await _safe_rebuild_tacit_docs(user_id, db, version)
    return profile_to_snapshot(profile)


async def get_tacit_context(
    user_id: str,
    db: AsyncSession,
    query: str | None = None,
    forbidden_topics: list | None = None,
    gate_trace: list[dict] | None = None,
) -> str:
    profile = await _get_active_profile(user_id, db)
    if not profile or (profile.confidence or 0) < HIGH_CONFIDENCE:
        append_gate_trace(
            gate_trace,
            source="tacit_profile",
            kept=False,
            reason="profile_unavailable_or_low_confidence",
            metadata={"confidence": profile.confidence if profile else 0},
        )
        return ""

    lines = []
    query_topics = set(classify_query_topics(query or ""))
    profile_data = profile.profile or {}
    for dimension in DIMENSION_ORDER:
        claims = _active_claims(profile_data.get(dimension, []), threshold=HIGH_CONFIDENCE)
        for claim in claims[:2]:
            claim_text = claim.get("claim") or ""
            if is_forbidden_text(claim_text, forbidden_topics):
                append_gate_trace(
                    gate_trace,
                    source="tacit_profile",
                    kept=False,
                    reason="forbidden",
                    text=claim_text,
                    metadata={"dimension": dimension},
                )
                continue
            decision = _explain_persona_claim_for_reply(dimension, claim_text, query_topics)
            if not decision["kept"]:
                append_gate_trace(
                    gate_trace,
                    source="tacit_profile",
                    kept=False,
                    reason=decision["reason"],
                    text=claim_text,
                    metadata={"dimension": dimension, **decision["metadata"]},
                )
                continue
            append_gate_trace(
                gate_trace,
                source="tacit_profile",
                kept=True,
                reason=decision["reason"],
                text=claim_text,
                metadata={"dimension": dimension, **decision["metadata"]},
            )
            lines.append(f"- {DIMENSIONS[dimension]}: {claim_text}")
        if len(lines) >= 6:
            break

    if not lines:
        return ""

    return "\n".join([
        "以下是跨会话沉淀出的默契画像，只用于理解用户、调整语气和支持方式，不要主动提及用户当前问题没有触发的具体事件：",
        *lines[:6],
    ])


async def get_profile_snapshot(user_id: str, db: AsyncSession) -> dict:
    profile = await _get_active_profile(user_id, db)
    if not profile:
        return {
            "summary": "",
            "version_no": 0,
            "confidence": 0,
            "updated_at": None,
            "dimensions": {},
        }
    return profile_to_snapshot(profile)


def _is_persona_claim_for_reply(dimension: str, claim: str, query_topics: set[str]) -> bool:
    return _explain_persona_claim_for_reply(dimension, claim, query_topics)["kept"]


def _explain_persona_claim_for_reply(dimension: str, claim: str, query_topics: set[str]) -> dict:
    if not claim:
        return _persona_gate_decision(False, "empty_claim")
    if _looks_like_specific_event(claim):
        return _persona_gate_decision(False, "specific_event")
    if dimension in ALWAYS_PERSONA_DIMENSIONS:
        return _persona_gate_decision(True, "persona_dimension")

    claim_topics = set(classify_query_topics(claim))
    if not query_topics:
        return _persona_gate_decision(False, "no_query_topics", {"claim_topics": sorted(claim_topics)})
    if not claim_topics:
        return _persona_gate_decision(
            dimension in {"routines"},
            "routine_without_topic" if dimension in {"routines"} else "no_claim_topics",
            {"claim_topics": [], "query_topics": sorted(query_topics)},
        )
    kept = bool(claim_topics & query_topics)
    return _persona_gate_decision(
        kept,
        "topic_overlap" if kept else "unrelated",
        {"claim_topics": sorted(claim_topics), "query_topics": sorted(query_topics)},
    )


def _persona_gate_decision(kept: bool, reason: str, metadata: dict | None = None) -> dict:
    return {"kept": kept, "reason": reason, "metadata": metadata or {}}


def _looks_like_specific_event(text: str) -> bool:
    time_words = (
        "今天",
        "明天",
        "后天",
        "大后天",
        "三天后",
        "下周",
        "上午",
        "下午",
        "晚上",
        "点",
        "截止",
        "ddl",
        "DDL",
    )
    event_words = ("面试", "考试", "会议", "预约", "提醒", "计划", "安排")
    return any(word in text for word in time_words) and any(word in text for word in event_words)


def profile_to_snapshot(profile: TacitProfile) -> dict:
    profile_data = profile.profile or {}
    summary = profile.summary or ""
    if _is_legacy_profile_summary(summary):
        summary = _profile_narrative_summary(profile_data)
    dimensions = {}
    for key in DIMENSION_ORDER:
        dimensions[key] = {
            "label": DIMENSIONS[key],
            "items": _active_claims(profile_data.get(key, []), threshold=0.35)[:5],
        }
    return {
        "summary": summary,
        "version_no": profile.version_no or 0,
        "confidence": round(profile.confidence or 0, 2),
        "horizon_start": profile.horizon_start.isoformat() if profile.horizon_start else None,
        "horizon_end": profile.horizon_end.isoformat() if profile.horizon_end else None,
        "last_analyzed_at": profile.last_analyzed_at.isoformat() if profile.last_analyzed_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "dimensions": dimensions,
    }


async def _get_active_profile(user_id: str, db: AsyncSession) -> TacitProfile | None:
    result = await db.execute(
        select(TacitProfile).where(TacitProfile.user_id == user_id, TacitProfile.status == "active")
    )
    return result.scalar_one_or_none()


async def _safe_rebuild_tacit_docs(user_id: str, db: AsyncSession, version: TacitProfileVersion | None = None) -> None:
    try:
        from app.services.memory_document_service import rebuild_delta_doc, rebuild_user_doc
        await rebuild_user_doc(user_id, db)
        await rebuild_delta_doc(user_id, db, version=version)
    except Exception as e:
        await db.rollback()
        print(f"[memory_doc] USER.md/DELTA.md 重建失败: {e}")


async def _summarize_messages(messages: list[Message]) -> dict:
    transcript = _build_transcript(messages)
    llm_payload = await _llm_session_summary(transcript)
    if llm_payload:
        return _normalize_summary_payload(llm_payload, transcript)
    return _heuristic_summary(transcript)


async def _llm_session_summary(transcript: str) -> dict | None:
    if not transcript:
        return None
    try:
        from app.services.model_gateway import gateway

        prompt = f"""请把这段伴行对话压缩成用于长期个性化画像的会话摘要。

只提取能帮助伴行更懂用户的稳定信息，不要记录隐私猜测，不要夸大。
返回 JSON，结构如下：
{{
  "summary": "一句到三句话概括本会话",
  "topics": ["主题1", "主题2"],
  "signals": {{
    "life_stage": [{{"claim": "用户近期处于什么阶段", "confidence": 0.0, "stability": "short|medium|long"}}],
    "long_term_goals": [],
    "routines": [],
    "decision_style": [],
    "emotional_patterns": [],
    "communication_style": [],
    "support_preferences": []
  }}
}}

对话：
{transcript[:6000]}
"""
        full = ""
        async for chunk in gateway.stream(prompt, system="你是伴行的长期画像摘要器，只输出 JSON。"):
            full += chunk
        return _extract_json_object(full)
    except Exception as e:
        print(f"[tacit] LLM 会话摘要失败: {e}")
        return None


def _normalize_summary_payload(payload: dict, transcript: str) -> dict:
    fallback = _heuristic_summary(transcript)
    summary = str(payload.get("summary") or fallback["summary"]).strip()
    topics = payload.get("topics")
    if not isinstance(topics, list):
        topics = fallback["topics"]
    signals = payload.get("signals")
    if not isinstance(signals, dict):
        signals = fallback["signals"]
    normalized_signals = _empty_profile()
    now_iso = datetime.now(timezone.utc).isoformat()
    for dimension in DIMENSION_ORDER:
        raw_items = signals.get(dimension, [])
        if not isinstance(raw_items, list):
            continue
        for raw in raw_items[:5]:
            if not isinstance(raw, dict):
                continue
            claim = str(raw.get("claim") or "").strip()
            if len(claim) < 4:
                continue
            normalized_signals[dimension].append({
                "claim": claim[:180],
                "confidence": _clamp_float(raw.get("confidence"), 0.45, 0.3, 0.85),
                "stability": raw.get("stability") if raw.get("stability") in {"short", "medium", "long"} else "medium",
                "status": "active",
                "evidence_count": 1,
                "first_seen": now_iso,
                "last_seen": now_iso,
            })
    if not any(normalized_signals.values()):
        normalized_signals = fallback["signals"]
    return {
        "summary": summary[:4000],
        "topics": [str(t)[:40] for t in topics if str(t).strip()][:12],
        "signals": normalized_signals,
    }


def _heuristic_summary(transcript: str) -> dict:
    user_text = _user_only_text(transcript)
    summary = _compact_text(user_text, 280) or "本会话暂无足够可沉淀的用户画像信息。"
    topics = []
    signals = _empty_profile()
    now_iso = datetime.now(timezone.utc).isoformat()
    cancelled_terms = _extract_cancelled_terms_from_text(user_text)

    def add(dimension: str, claim: str, confidence: float = 0.48, stability: str = "medium"):
        signals[dimension].append({
            "claim": claim,
            "confidence": confidence,
            "stability": stability,
            "status": "active",
            "evidence_count": 1,
            "first_seen": now_iso,
            "last_seen": now_iso,
        })

    if _has_any(user_text, ("面试", "求职", "简历", "offer", "岗位", "招聘")):
        topics.append("求职/面试")
        add("life_stage", "用户近期处于求职或面试准备阶段。", 0.58, "short")
        add("support_preferences", "用户在求职相关问题上可能更需要清晰步骤和可执行准备。", 0.5, "medium")
    if _has_any(user_text, ("考试", "备考", "考研", "考公", "刷题")):
        topics.append("备考")
        add("life_stage", "用户近期处于备考或学习冲刺阶段。", 0.55, "short")
    if _has_any(user_text, ("项目", "上线", "需求", "bug", "代码", "分支", "提交", "PR")):
        topics.append("项目推进")
        add("life_stage", "用户近期在推进具体项目或开发任务。", 0.55, "short")
    if _has_any(user_text, ("跑步", "健身", "运动", "公里", "训练")):
        topics.append("运动")
        activity_claim = _activity_claim_from_text(user_text, cancelled_terms)
        if activity_claim:
            add("routines", activity_claim, 0.52, "medium")
    if _has_any(user_text, ("早睡", "熬夜", "睡眠", "失眠", "作息")):
        topics.append("作息")
        add("routines", "用户会关注作息和睡眠状态。", 0.52, "medium")
    if _has_any(user_text, ("焦虑", "压力", "累", "烦", "崩", "紧张")):
        topics.append("压力状态")
        add("emotional_patterns", "用户在压力场景下容易出现疲惫、紧张或焦虑感。", 0.5, "short")
    if _has_any(user_text, ("纠结", "犹豫", "怎么选", "选择", "担心")):
        add("decision_style", "用户面对重要选择时倾向反复权衡风险和收益。", 0.5, "medium")
    if _has_any(user_text, ("直接", "别废话", "简洁", "具体", "步骤", "计划")):
        add("communication_style", "用户偏好直接、具体、可执行的沟通方式。", 0.55, "long")
    if _has_any(user_text, ("提醒我", "督促", "别催", "陪我", "鼓励")):
        add("support_preferences", "用户对提醒、陪伴或督促方式有明确感受，需要控制力度。", 0.5, "medium")

    return {
        "summary": summary,
        "topics": topics[:12],
        "signals": signals,
    }


def _collect_evidence(summaries: list[SessionSummary]) -> dict:
    evidence = _empty_profile()
    for item in summaries:
        source_time = item.ended_at or item.updated_at or datetime.now(timezone.utc)
        source_time_iso = source_time.isoformat()
        refs = [{"session_id": str(item.session_id), "summary_id": str(item.id)}]
        signals = item.signals or {}
        for dimension in DIMENSION_ORDER:
            for raw in signals.get(dimension, []) or []:
                if not isinstance(raw, dict):
                    continue
                claim = str(raw.get("claim") or "").strip()
                if len(claim) < 4:
                    continue
                existing = _find_claim(evidence[dimension], claim)
                if not existing:
                    existing = {
                        "claim": claim[:180],
                        "confidence": _clamp_float(raw.get("confidence"), 0.45, 0.2, 0.9),
                        "stability": raw.get("stability") if raw.get("stability") in {"short", "medium", "long"} else "medium",
                        "status": "active",
                        "evidence_count": 0,
                        "first_seen": source_time_iso,
                        "last_seen": source_time_iso,
                        "evidence_refs": [],
                    }
                    evidence[dimension].append(existing)
                existing["evidence_count"] = int(existing.get("evidence_count") or 0) + 1
                existing["confidence"] = min(0.92, max(existing.get("confidence") or 0, _clamp_float(raw.get("confidence"), 0.45)) + 0.06)
                existing["last_seen"] = max(str(existing.get("last_seen") or ""), source_time_iso)
                existing["evidence_refs"] = _merge_refs(existing.get("evidence_refs", []), refs)
    return evidence


async def _load_co_created_memories(user_id: str, db: AsyncSession, now: datetime) -> list[MemoryItem]:
    result = await db.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.layer == "co_created",
            MemoryItem.status == "active",
            MemoryItem.user_confirmed.is_(True),
        )
        .order_by(MemoryItem.updated_at.desc())
        .limit(40)
    )
    items = []
    for item in result.scalars().all():
        if item.memory_type == "event" and item.expires_at and item.expires_at < now - timedelta(days=3):
            continue
        items.append(item)
    return items


def _collect_co_created_evidence(memories: list[MemoryItem], now: datetime) -> dict:
    evidence = _empty_profile()
    for item in memories:
        source_time = item.updated_at or item.created_at or now
        source_time_iso = source_time.isoformat()
        refs = [{"memory_id": str(item.id), "source_type": "co_created"}]
        summary = (item.summary or "").strip()
        if not summary:
            continue
        for dimension, claim, confidence, stability in _signals_from_co_created_memory(item, source_time):
            existing = _find_claim(evidence[dimension], claim)
            if not existing:
                existing = {
                    "claim": claim[:180],
                    "confidence": confidence,
                    "stability": stability,
                    "status": "active",
                    "evidence_count": 0,
                    "first_seen": source_time_iso,
                    "last_seen": source_time_iso,
                    "evidence_refs": [],
                }
                evidence[dimension].append(existing)
            existing["evidence_count"] = int(existing.get("evidence_count") or 0) + 1
            existing["confidence"] = min(0.94, max(existing.get("confidence") or 0, confidence) + 0.04)
            existing["last_seen"] = max(str(existing.get("last_seen") or ""), source_time_iso)
            existing["evidence_refs"] = _merge_refs(existing.get("evidence_refs", []), refs)
    return evidence


def _signals_from_co_created_memory(item: MemoryItem, source_time: datetime) -> list[tuple[str, str, float, str]]:
    summary = _compact_text(item.summary or "", 160)
    memory_type = item.memory_type or "general"
    content = item.content or {}
    if content.get("lifecycle") == "superseded":
        return []
    text = f"{summary}\n{json.dumps(content, ensure_ascii=False)}"
    cancelled_terms = _extract_cancelled_terms_from_text(text)
    signals: list[tuple[str, str, float, str]] = []

    if memory_type == "preference":
        signals.append(("support_preferences", f"用户明确表达过偏好：{summary}", 0.72, "long"))
    elif memory_type == "boundary":
        signals.append(("support_preferences", f"用户明确设定过边界或禁区：{summary}", 0.78, "long"))
    elif memory_type == "routine":
        if _has_replacement_intent(text) or _has_any(text, ("今天", "明天", "后天", "这次", "之后")):
            signals.append(("long_term_goals", f"用户近期明确提到过生活或运动安排：{summary}", 0.56, "short"))
        else:
            signals.append(("routines", f"用户明确提到过稳定习惯或节奏：{summary}", 0.7, "medium"))
    elif memory_type == "profile":
        signals.append(("life_stage", f"用户明确提供过个人背景：{summary}", 0.66, "long"))
    elif memory_type == "event":
        stability = "short"
        confidence = 0.58
        if item.event_at and item.event_at >= source_time:
            signals.append(("life_stage", f"用户近期有阶段性事项：{summary}", confidence, stability))
    elif memory_type == "insight":
        signals.append(("decision_style", f"用户曾确认过一个自我理解：{summary}", 0.64, "medium"))

    if _has_any(text, ("面试", "求职", "简历", "offer", "岗位", "招聘")):
        signals.append(("life_stage", "用户近期围绕求职或面试准备投入注意力。", 0.62, "short"))
    if _has_any(text, ("目标", "计划", "想要", "希望", "准备", "正在")):
        signals.append(("long_term_goals", f"用户明确提到过目标或计划：{summary}", 0.62, "medium"))
    if _has_any(text, ("跑步", "健身", "运动", "公里", "训练")):
        activity_claim = _activity_claim_from_text(text, cancelled_terms)
        if activity_claim:
            signals.append(("routines", activity_claim, 0.62, "medium"))
    if _has_any(text, ("早睡", "熬夜", "睡眠", "失眠", "作息")):
        signals.append(("routines", "用户会关注作息和睡眠状态。", 0.6, "medium"))
    if _has_any(text, ("焦虑", "压力", "累", "烦", "紧张")):
        signals.append(("emotional_patterns", "用户在压力场景下容易出现疲惫、紧张或焦虑感。", 0.58, "short"))
    if _has_any(text, ("纠结", "犹豫", "怎么选", "选择", "担心")):
        signals.append(("decision_style", "用户面对重要选择时倾向反复权衡风险和收益。", 0.58, "medium"))
    if _has_any(text, ("直接", "别废话", "简洁", "具体", "步骤", "计划")):
        signals.append(("communication_style", "用户偏好直接、具体、可执行的沟通方式。", 0.68, "long"))

    return signals


def _combine_evidence(primary: dict, secondary: dict) -> dict:
    combined = _ensure_profile_shape(deepcopy(primary))
    for dimension in DIMENSION_ORDER:
        for raw in secondary.get(dimension, []):
            existing = _find_claim(combined[dimension], raw.get("claim", ""))
            if not existing:
                combined[dimension].append(deepcopy(raw))
                continue
            existing["confidence"] = min(0.95, max(existing.get("confidence") or 0, raw.get("confidence") or 0) + 0.05)
            existing["evidence_refs"] = _merge_refs(existing.get("evidence_refs", []), raw.get("evidence_refs", []))
            existing["evidence_count"] = max(int(existing.get("evidence_count") or 0), len(existing.get("evidence_refs", [])))
            existing["last_seen"] = max(str(existing.get("last_seen") or ""), str(raw.get("last_seen") or ""))
    return combined


def _merge_profile(base_profile: dict, evidence: dict, now: datetime) -> tuple[dict, dict]:
    merged = _ensure_profile_shape(deepcopy(base_profile))
    delta = _empty_profile()
    now_iso = now.isoformat()
    for dimension in DIMENSION_ORDER:
        for raw in evidence.get(dimension, []):
            existing = _find_claim(merged[dimension], raw["claim"])
            if existing:
                old_confidence = existing.get("confidence") or 0
                merged_refs = _merge_refs(existing.get("evidence_refs", []), raw.get("evidence_refs", []))
                existing["confidence"] = min(0.95, max(old_confidence, raw.get("confidence") or 0) + 0.04)
                existing["evidence_count"] = max(int(existing.get("evidence_count") or 0), len(merged_refs))
                existing["last_seen"] = raw.get("last_seen") or now_iso
                existing["status"] = "active"
                existing["evidence_refs"] = merged_refs
                change_type = "reinforced"
            else:
                existing = deepcopy(raw)
                existing.setdefault("first_seen", raw.get("first_seen") or now_iso)
                existing.setdefault("last_seen", raw.get("last_seen") or now_iso)
                existing.setdefault("status", "active")
                merged[dimension].append(existing)
                change_type = "added"
            delta[dimension].append({
                "claim": existing.get("claim"),
                "change": change_type,
                "confidence": round(existing.get("confidence") or 0, 2),
            })
        merged[dimension] = sorted(
            [c for c in merged[dimension] if c.get("status") != "archived"],
            key=lambda c: (c.get("confidence") or 0, c.get("evidence_count") or 0),
            reverse=True,
        )[:8]
    return merged, delta


def _apply_decay(profile_data: dict, now: datetime) -> tuple[dict, dict]:
    profile_data = _ensure_profile_shape(deepcopy(profile_data))
    decay_log = _empty_profile()
    for dimension in DIMENSION_ORDER:
        kept = []
        for claim in profile_data[dimension]:
            last_seen = _parse_datetime(claim.get("last_seen")) or now
            age_days = max(0, (now - last_seen).days)
            stability = claim.get("stability") if claim.get("stability") in {"short", "medium", "long"} else "medium"
            threshold = {"short": 14, "medium": 30, "long": 90}[stability]
            archive_threshold = threshold * 2
            old_confidence = claim.get("confidence") or 0
            if age_days > archive_threshold and stability != "long":
                claim["status"] = "archived"
                claim["confidence"] = max(0, old_confidence - 0.25)
            elif age_days > threshold:
                claim["status"] = "cooling"
                claim["confidence"] = max(0.2, old_confidence - 0.12)
            if claim.get("status") != "archived":
                kept.append(claim)
            if claim.get("confidence") != old_confidence:
                decay_log[dimension].append({
                    "claim": claim.get("claim"),
                    "from": round(old_confidence, 2),
                    "to": round(claim.get("confidence") or 0, 2),
                    "age_days": age_days,
                })
        profile_data[dimension] = kept
    return profile_data, decay_log


def _collect_replacement_terms(memories: list[MemoryItem]) -> set[str]:
    terms: set[str] = set()
    for item in memories:
        content = item.content or {}
        replacement = content.get("replacement") if isinstance(content.get("replacement"), dict) else {}
        for term in replacement.get("cancelled_terms") or []:
            if isinstance(term, str) and term.strip():
                terms.add(term.strip())
        terms.update(_extract_cancelled_terms_from_text(f"{item.summary or ''}\n{json.dumps(content, ensure_ascii=False)}"))
    return terms


def _apply_explicit_replacements(profile_data: dict, terms: set[str], now: datetime) -> tuple[dict, dict]:
    if not terms:
        return profile_data, _empty_profile()

    profile_data = _ensure_profile_shape(deepcopy(profile_data))
    replacement_log = _empty_profile()
    now_iso = now.isoformat()
    for dimension in DIMENSION_ORDER:
        kept = []
        for claim in profile_data[dimension]:
            text = str(claim.get("claim") or "")
            matched = sorted(term for term in terms if term in text)
            if matched and claim.get("status", "active") != "archived":
                old_confidence = claim.get("confidence") or 0
                claim["status"] = "archived"
                claim["confidence"] = max(0.0, old_confidence - 0.35)
                claim["replaced_by_terms"] = matched
                claim["replaced_at"] = now_iso
                replacement_log[dimension].append({
                    "claim": claim.get("claim"),
                    "from": round(old_confidence, 2),
                    "to": round(claim.get("confidence") or 0, 2),
                    "terms": matched,
                    "reason": "explicit_replacement",
                })
            if claim.get("status") != "archived":
                kept.append(claim)
        profile_data[dimension] = kept
    return profile_data, replacement_log


def _combine_profile_logs(primary: dict, secondary: dict) -> dict:
    combined = _ensure_profile_shape(deepcopy(primary))
    for dimension in DIMENSION_ORDER:
        combined[dimension].extend(secondary.get(dimension, []))
    return combined


async def _profile_summary(profile_data: dict) -> str:
    fallback = _profile_narrative_summary(profile_data)
    llm_summary = await _llm_profile_summary(profile_data, fallback)
    return (llm_summary or fallback)[:800]


async def _llm_profile_summary(profile_data: dict, fallback: str) -> str | None:
    evidence = _profile_evidence_brief(profile_data)
    if not evidence:
        return None
    try:
        from app.services.model_gateway import gateway

        prompt = f"""请把下面这些长期画像证据整合成一段写给用户看的默契画像。

要求：
- 用第二人称“你”，像伴行逐渐懂这个人一样表达
- 写 2 到 4 句自然段，不要列清单，不要出现“近期阶段/长期目标/行为习惯”等字段名
- 不是简单复述证据，要说明这个人的状态、节奏、倾向，以及伴行应该如何靠近他
- 不做医学、身份、价值判断，不夸大不确定信息
- 如果证据很少，要保守表达
- 只输出正文

当前兜底画像：
{fallback}

画像证据：
{evidence}
"""
        full = ""
        async for chunk in gateway.stream(prompt, system="你是伴行的长期人物画像整合器，只写自然、克制、可给用户看的画像正文。"):
            full += chunk
        summary = _sanitize_profile_summary(full)
        return summary or None
    except Exception as e:
        print(f"[tacit] LLM 画像整合失败: {e}")
        return None


def _profile_narrative_summary(profile_data: dict) -> str:
    claims = _top_claims_by_dimension(profile_data, threshold=0.45)
    if not any(claims.values()):
        return "伴行正在形成对你的长期理解。"

    sentences = []
    stage = _claim_text(claims, "life_stage", 0)
    goals = _claim_text(claims, "long_term_goals", 0)
    routine = _claim_text(claims, "routines", 0)
    decision = _claim_text(claims, "decision_style", 0)
    emotion = _claim_text(claims, "emotional_patterns", 0)
    communication = _claim_text(claims, "communication_style", 0)
    support = _claim_text(claims, "support_preferences", 0)

    if stage and goals:
        sentences.append(f"最近的你主要围绕{_clean_claim(stage)}展开，同时也有一个明确的近期事项：{_clean_claim(goals)}。")
    elif stage:
        sentences.append(f"最近的你主要把注意力放在{_clean_claim(stage)}上。")
    elif goals:
        sentences.append(f"你最近有一个比较明确的目标或安排：{_clean_claim(goals)}。")

    rhythm_parts = []
    if routine:
        rhythm_parts.append(_routine_phrase(routine))
    if decision:
        rhythm_parts.append(_decision_phrase(decision))
    if rhythm_parts:
        rhythm_sentence = rhythm_parts[0] if len(rhythm_parts) == 1 else "；".join(rhythm_parts)
        sentences.append(f"从互动里看，{rhythm_sentence}，这比单个事实更像是你反复呈现出来的做事方式。")

    inner_parts = []
    if emotion:
        inner_parts.append(_clean_claim(emotion))
    if communication:
        inner_parts.append(_clean_claim(communication))
    if inner_parts:
        sentences.append(f"你表达问题时会透露出{_join_natural(inner_parts)}，所以伴行需要把回应落在真实处境里，而不是只给抽象建议。")

    if support:
        sentences.append(f"陪你时，伴行更适合{_support_phrase(support)}，在需要时给出清晰、适度、不过度打扰的支持。")

    if not sentences:
        flattened = [_clean_claim(item.get("claim", "")) for section in claims.values() for item in section[:2]]
        sentences.append(f"从最近几次互动看，你身上比较稳定地呈现出{_join_natural(flattened[:3])}。")

    return _sanitize_profile_summary("".join(sentences))


def _profile_evidence_brief(profile_data: dict) -> str:
    rows = []
    claims = _top_claims_by_dimension(profile_data, threshold=0.42)
    for dimension in DIMENSION_ORDER:
        for item in claims.get(dimension, [])[:3]:
            claim = _compact_text(str(item.get("claim") or ""), 160)
            if not claim:
                continue
            confidence = round(float(item.get("confidence") or 0), 2)
            count = int(item.get("evidence_count") or 1)
            rows.append(f"- {DIMENSIONS[dimension]}：{claim}（置信度 {confidence}，证据 {count} 次）")
    return "\n".join(rows[:16])


def _top_claims_by_dimension(profile_data: dict, threshold: float) -> dict[str, list[dict]]:
    return {
        dimension: _active_claims(profile_data.get(dimension, []), threshold=threshold)
        for dimension in DIMENSION_ORDER
    }


def _claim_text(claims: dict[str, list[dict]], dimension: str, index: int) -> str:
    items = claims.get(dimension, [])
    if index >= len(items):
        return ""
    return str(items[index].get("claim") or "")


def _clean_claim(text: str) -> str:
    cleaned = _compact_text(text, 120)
    replacements = (
        ("用户近期处于", ""),
        ("用户近期围绕", ""),
        ("用户近期在", ""),
        ("投入注意力", ""),
        ("用户明确提到过", ""),
        ("用户明确表达过", ""),
        ("用户明确设定过", ""),
        ("用户明确提供过", ""),
        ("用户曾确认过", ""),
        ("用户会关注", ""),
        ("用户偏好", ""),
        ("用户面对", "面对"),
        ("用户在", "在"),
        ("用户", "你"),
        ("目标或计划：", ""),
    )
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.strip(" ：:；;，。 ")
    if cleaned.startswith("过"):
        cleaned = cleaned[1:]
    return cleaned or text


def _routine_phrase(text: str) -> str:
    cleaned = _clean_claim(text)
    if "健身" in cleaned:
        return "日常节奏开始向健身和身体状态靠拢"
    if "跑步" in cleaned:
        return "日常节奏里曾稳定出现跑步和身体状态管理"
    if "运动" in cleaned or "训练" in cleaned:
        return "日常里会给运动和身体状态留位置"
    if "作息" in cleaned or "睡眠" in cleaned:
        return "日常节奏里会关注作息和睡眠"
    return f"日常节奏里有{cleaned}"


def _decision_phrase(text: str) -> str:
    cleaned = _clean_claim(text)
    if "风险和收益" in cleaned:
        return "做重要选择前，会反复权衡风险和收益"
    if cleaned.startswith("面对"):
        return cleaned
    return f"做事时呈现出{cleaned}"


def _support_phrase(text: str) -> str:
    cleaned = _clean_claim(text)
    if "清晰步骤" in cleaned or "可执行" in cleaned:
        return "把建议拆成清晰、可执行的步骤"
    if "提醒" in cleaned or "督促" in cleaned:
        return "控制提醒和督促的力度"
    return f"记住{cleaned}"


def _join_natural(parts: list[str]) -> str:
    compacted = [_compact_text(part, 80).strip(" ：:；;，。 ") for part in parts if part]
    if not compacted:
        return ""
    if len(compacted) == 1:
        return compacted[0]
    return "，也有".join(compacted)


def _sanitize_profile_summary(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip().strip('"').strip("'"))
    cleaned = re.sub(r"^(默契画像|画像|总结)[:：]\s*", "", cleaned)
    cleaned = cleaned.replace("用户：", "")
    return cleaned[:800].strip()


def _is_legacy_profile_summary(text: str) -> bool:
    if not text:
        return False
    label_hits = sum(1 for label in DIMENSIONS.values() if f"{label}：" in text or f"{label}:" in text)
    return label_hits >= 2


def _profile_confidence(profile_data: dict) -> float:
    values = []
    for dimension in DIMENSION_ORDER:
        values.extend((c.get("confidence") or 0) for c in profile_data.get(dimension, []) if c.get("status") == "active")
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _active_claims(claims: list[dict], threshold: float) -> list[dict]:
    return [
        c for c in sorted(claims or [], key=lambda x: (x.get("confidence") or 0, x.get("evidence_count") or 0), reverse=True)
        if c.get("status", "active") in {"active", "cooling"} and (c.get("confidence") or 0) >= threshold
    ]


def _build_transcript(messages: list[Message]) -> str:
    rows = []
    for msg in messages[-60:]:
        role = "用户" if msg.role == "user" else "伴行"
        rows.append(f"{role}: {_compact_text(msg.content, 500)}")
    return "\n".join(rows)


def _user_only_text(transcript: str) -> str:
    lines = []
    for line in transcript.splitlines():
        if line.startswith("用户:"):
            lines.append(line[3:].strip())
    return "\n".join(lines)


def _empty_profile() -> dict:
    return {key: [] for key in DIMENSION_ORDER}


def _ensure_profile_shape(profile_data: dict | None) -> dict:
    shaped = _empty_profile()
    if not isinstance(profile_data, dict):
        return shaped
    for key in DIMENSION_ORDER:
        value = profile_data.get(key, [])
        shaped[key] = value if isinstance(value, list) else []
    return shaped


def _find_claim(claims: list[dict], claim: str) -> dict | None:
    needle = _normalize_claim(claim)
    for item in claims:
        current = _normalize_claim(item.get("claim", ""))
        if current == needle or current in needle or needle in current:
            return item
    return None


def _normalize_claim(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").casefold())


def _merge_refs(existing: list[dict], refs: list[dict]) -> list[dict]:
    seen = set()
    merged = []
    for ref in [*(existing or []), *(refs or [])]:
        key = (ref.get("source_type"), ref.get("session_id"), ref.get("summary_id"), ref.get("memory_id"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(ref)
    return merged[-8:]


def _extract_json_object(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _activity_claim_from_text(text: str, cancelled_terms: set[str]) -> str:
    if "健身" in text and "健身" not in cancelled_terms:
        return "用户会关注健身、运动或身体状态。"
    if "跑步" in text and "跑步" not in cancelled_terms:
        return "用户会关注跑步、运动或身体状态。"
    if _has_any(text, ("运动", "训练", "公里")):
        return "用户会关注运动或身体状态。"
    return ""


def _extract_cancelled_terms_from_text(text: str) -> set[str]:
    if not _has_replacement_intent(text):
        return set()

    spans: list[str] = []
    for pattern in (
        r"(?:取消|停止|暂停|放弃|停掉|不再|别再|不用|不要|先不)([^，。！？；、\n]{1,24})",
        r"([^，。！？；、\n]{1,24}?)(?:取消了?|停止了?|暂停了?|放弃了?|停掉了?|不做了?|不去了?|不用了?|不要了?)",
        r"(?:把|将)?([^，。！？；、\n]{1,24}?)(?:改为|改成|换成|替换成|改去|改做)",
    ):
        spans.extend(match.group(1) for match in re.finditer(pattern, text or ""))

    terms: set[str] = set()
    for span in spans:
        terms.update(_extract_topic_terms(span))
    return {term for term in terms if len(term) >= 2}


def _extract_topic_terms(phrase: str) -> set[str]:
    phrase = re.sub(r"\s+", "", phrase or "")
    known_terms = (
        "跑步",
        "健身",
        "运动",
        "训练",
        "面试",
        "考试",
        "会议",
        "求职",
        "简历",
        "香蕉",
        "橘子",
        "水果",
        "早睡",
        "熬夜",
        "睡眠",
        "学习",
        "项目",
        "代码",
        "提醒",
    )
    terms = {term for term in known_terms if term in phrase}
    if terms:
        return terms

    cleaned = phrase
    for word in (
        "用户",
        "自己",
        "我的",
        "我",
        "原来",
        "之前",
        "当前",
        "现在",
        "今天",
        "明天",
        "后天",
        "之后",
        "以后",
        "这次",
        "计划",
        "安排",
        "习惯",
        "目标",
        "需要",
        "准备",
        "已经",
        "还是",
        "那个",
        "这个",
        "一些",
        "的",
        "了",
        "去",
        "做",
        "要",
        "会",
    ):
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.strip("，。！？；、 ")
    if 2 <= len(cleaned) <= 12:
        return {cleaned}
    return set()


def _has_replacement_intent(text: str) -> bool:
    return bool(re.search(r"(取消|停止|暂停|放弃|停掉|不再|别再|不用|不要|不做了|不去了|改为|改成|换成|替换成|改去|改做)", text or ""))


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _compact_text(text: str, limit: int) -> str:
    compacted = " ".join((text or "").split())
    return compacted[:limit]


def _clamp_float(value, default: float = 0.0, low: float = 0.0, high: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
