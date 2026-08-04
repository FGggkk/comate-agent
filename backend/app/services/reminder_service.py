import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder

APP_TZ = timezone(timedelta(hours=8))
REMINDER_TRIGGERS = (
    "提醒我",
    "叫我",
    "喊我",
    "通知我",
    "帮我提醒",
    "记得提醒",
    "到点提醒",
    "到时候提醒",
)
REMINDER_NEGATIONS = ("不用提醒", "不要提醒", "别提醒", "不提醒", "无需提醒", "先不提醒")


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(reminder: Reminder) -> dict:
    return {
        "success": True,
        "id": str(reminder.id),
        "content": reminder.content,
        "remind_at": reminder.remind_at.isoformat(),
        "triggered": reminder.triggered,
    }


async def _find_existing(user_id: str, content: str, remind_at: datetime, db: AsyncSession) -> Reminder | None:
    result = await db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.content == content,
            Reminder.remind_at == remind_at,
        ).limit(1)
    )
    return result.scalar_one_or_none()


def parse_reminder_request(text: str) -> dict | None:
    """从显式提醒请求中生成提醒草稿，不做数据库写入。"""
    raw_text = (text or "").strip()
    if not raw_text or any(word in raw_text for word in REMINDER_NEGATIONS):
        return None
    if not any(word in raw_text for word in REMINDER_TRIGGERS):
        return None

    remind_at, estimated_time = _infer_reminder_datetime(raw_text)
    content = _extract_reminder_content(raw_text)
    if not content:
        content = _strip_reminder_noise(raw_text)
    if not content:
        content = "这件事"

    return {
        "content": content[:500],
        "remind_at": remind_at.isoformat(),
        "estimated_time": estimated_time,
        "label": f"提醒：{content[:40]}（{_format_local_reminder_time(remind_at)}）",
    }


async def create(user_id: str, content: str, remind_at: datetime, db: AsyncSession) -> dict:
    normalized_content = (content or "").strip()
    if not normalized_content:
        return {"success": False, "message": "提醒内容不能为空"}
    if len(normalized_content) > 500:
        return {"success": False, "message": "提醒内容不能超过 500 字"}

    normalized_remind_at = _as_aware_utc(remind_at)
    if normalized_remind_at <= datetime.now(timezone.utc):
        return {"success": False, "message": "提醒时间需要晚于现在"}

    existing = await _find_existing(user_id, normalized_content, normalized_remind_at, db)
    if existing:
        data = _serialize(existing)
        data["already_exists"] = True
        return data

    reminder = Reminder(user_id=user_id, content=normalized_content, remind_at=normalized_remind_at)
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return _serialize(reminder)


async def create_once(user_id: str, content: str, remind_at: datetime, db: AsyncSession) -> dict:
    normalized_content = (content or "").strip()
    normalized_remind_at = _as_aware_utc(remind_at)
    existing = await _find_existing(user_id, normalized_content, normalized_remind_at, db)
    if existing:
        data = _serialize(existing)
        data["already_exists"] = True
        return data
    return await create(user_id, normalized_content, normalized_remind_at, db)


async def list_reminders(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.remind_at.asc())
    )
    items = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "content": r.content,
            "remind_at": r.remind_at.isoformat(),
            "triggered": r.triggered,
        }
        for r in items
    ]


async def delete_reminder(user_id: str, reminder_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        delete(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        return {"success": False, "message": "提醒不存在或无权操作"}
    return {"success": True}


async def get_due_reminders(user_id: str, db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.triggered == False,
            Reminder.remind_at <= now,
        )
    )
    items = result.scalars().all()
    due = []
    for r in items:
        r.triggered = True
        due.append({"id": str(r.id), "content": r.content, "remind_at": r.remind_at.isoformat()})

    if due:
        await db.commit()

    return due


def _infer_reminder_datetime(text: str) -> tuple[datetime, bool]:
    now = datetime.now(APP_TZ)

    relative_match = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*(分钟|小时|天)后", text)
    if relative_match:
        amount = _parse_chinese_number(relative_match.group(1))
        unit = relative_match.group(2)
        if amount > 0:
            if unit == "分钟":
                return (now + timedelta(minutes=amount)).astimezone(timezone.utc), False
            if unit == "小时":
                return (now + timedelta(hours=amount)).astimezone(timezone.utc), False
            if unit == "天":
                target = now + timedelta(days=amount)
                target = target.replace(hour=9, minute=0, second=0, microsecond=0)
                return target.astimezone(timezone.utc), True

    target_date = _parse_reminder_date(text, now) or now.date()
    hour, minute, has_time = _parse_reminder_time(text)
    if not has_time:
        hour, minute = _default_reminder_time(text)

    local = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=APP_TZ)
    if local <= now:
        local = local + timedelta(days=1)
    return local.astimezone(timezone.utc), not has_time


def _parse_reminder_date(text: str, now: datetime):
    if "大后天" in text:
        return (now + timedelta(days=3)).date()
    if "后天" in text:
        return (now + timedelta(days=2)).date()
    if any(word in text for word in ("明天", "明早", "明晚")):
        return (now + timedelta(days=1)).date()
    if any(word in text for word in ("今天", "今晚")):
        return now.date()

    md_match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", text)
    if md_match:
        month, day = (int(part) for part in md_match.groups())
        candidate = datetime(now.year, month, day, tzinfo=APP_TZ)
        if candidate.date() < now.date():
            candidate = datetime(now.year + 1, month, day, tzinfo=APP_TZ)
        return candidate.date()
    return None


def _parse_reminder_time(text: str) -> tuple[int, int, bool]:
    colon_match = re.search(r"(\d{1,2})[:：](\d{2})", text)
    if colon_match:
        hour, minute = (int(part) for part in colon_match.groups())
        return _normalize_hour(hour, text), minute, True

    hour_match = re.search(r"(凌晨|早上|上午|中午|下午|晚上|今晚|明早|明晚)?\s*(\d{1,2}|[一二两三四五六七八九十]+)\s*点半?", text)
    if hour_match:
        period, raw_hour = hour_match.groups()
        hour = _parse_chinese_number(raw_hour)
        minute = 30 if "点半" in hour_match.group(0) else 0
        return _normalize_hour(hour, period or text), minute, True
    return 9, 0, False


def _default_reminder_time(text: str) -> tuple[int, int]:
    if any(word in text for word in ("睡前", "睡觉前")):
        return 22, 0
    if any(word in text for word in ("晚上", "今晚", "明晚", "晚饭后", "饭后")):
        return 20, 0
    if any(word in text for word in ("下午",)):
        return 15, 0
    if any(word in text for word in ("中午", "午饭后")):
        return 12, 0
    return 9, 0


def _extract_reminder_content(text: str) -> str:
    trigger_pattern = "|".join(re.escape(word) for word in REMINDER_TRIGGERS)
    match = re.search(rf"(?:{trigger_pattern})(?P<content>.+)", text)
    if match:
        return _strip_reminder_noise(match.group("content"))
    return _strip_reminder_noise(text)


def _strip_reminder_noise(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text or "")
    trigger_pattern = "|".join(re.escape(word) for word in REMINDER_TRIGGERS)
    cleaned = re.sub(trigger_pattern, "", cleaned)
    cleaned = re.sub(r"(\d+|[一二两三四五六七八九十]+)\s*(分钟|小时|天)后", "", cleaned)
    cleaned = re.sub(r"(今天|今晚|明天|明早|明晚|后天|大后天|早上|上午|中午|下午|晚上|睡前|睡觉前|晚饭后|午饭后|饭后)", "", cleaned)
    cleaned = re.sub(r"\d{1,2}[:：]\d{2}", "", cleaned)
    cleaned = re.sub(r"(凌晨|早上|上午|中午|下午|晚上)?\s*(\d{1,2}|[一二两三四五六七八九十]+)\s*点半?", "", cleaned)
    cleaned = re.sub(r"^(我|一下|要|记得|到点|到时候|的时候|后)+", "", cleaned)
    return cleaned.strip("，。！？；、,.!? ")


def _normalize_hour(hour: int, context: str) -> int:
    if any(word in context for word in ("下午", "晚上", "今晚", "明晚")) and hour < 12:
        return hour + 12
    if "中午" in context and hour < 11:
        return hour + 12
    if "凌晨" in context and hour == 12:
        return 0
    return hour


def _parse_chinese_number(raw: str) -> int:
    if raw.isdigit():
        return int(raw)
    mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if raw == "十":
        return 10
    if raw.startswith("十"):
        return 10 + mapping.get(raw[-1], 0)
    if "十" in raw:
        left, _, right = raw.partition("十")
        return mapping.get(left, 0) * 10 + mapping.get(right, 0)
    return mapping.get(raw, 0)


def _format_local_reminder_time(value: datetime) -> str:
    local = value.astimezone(APP_TZ)
    now = datetime.now(APP_TZ)
    tomorrow = now + timedelta(days=1)
    time_text = f"{local.hour:02d}:{local.minute:02d}"
    if local.date() == now.date():
        return f"今天 {time_text}"
    if local.date() == tomorrow.date():
        return f"明天 {time_text}"
    return f"{local.month}月{local.day}日 {time_text}"
