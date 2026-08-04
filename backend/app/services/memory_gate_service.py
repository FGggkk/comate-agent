import json
import logging
from collections import Counter
from typing import Any


logger = logging.getLogger(__name__)
MAX_TRACE_TEXT = 90
MAX_TRACE_ITEMS = 40


def append_gate_trace(
    trace: list[dict] | None,
    *,
    source: str,
    kept: bool,
    reason: str,
    text: str = "",
    item_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one memory gate decision for debug observability."""
    if trace is None or len(trace) >= MAX_TRACE_ITEMS:
        return

    trace.append({
        "source": source,
        "kept": kept,
        "reason": reason,
        "item_id": item_id,
        "text": _clip_trace_text(text),
        "metadata": metadata or {},
    })


def summarize_gate_trace(trace: list[dict] | None) -> dict:
    items = trace or []
    by_source = Counter(item.get("source") or "unknown" for item in items)
    by_reason = Counter(item.get("reason") or "unknown" for item in items)
    kept = sum(1 for item in items if item.get("kept"))
    return {
        "total": len(items),
        "kept": kept,
        "filtered": len(items) - kept,
        "by_source": dict(by_source),
        "by_reason": dict(by_reason),
    }


def log_gate_trace(
    trace: list[dict] | None,
    *,
    enabled: bool,
    user_id: str,
    query: str,
    query_topics: list[str] | None = None,
) -> None:
    if not enabled or not trace:
        return

    payload = {
        "user_id": user_id,
        "query": _clip_trace_text(query),
        "query_topics": query_topics or [],
        "summary": summarize_gate_trace(trace),
        "items": trace[:MAX_TRACE_ITEMS],
    }
    message = f"[memory-gate] {json.dumps(payload, ensure_ascii=False)}"
    logger.info(message)
    print(message)


def _clip_trace_text(text: str | None) -> str:
    compacted = " ".join((text or "").split())
    return compacted[:MAX_TRACE_TEXT]
