from pydantic import BaseModel


class SSEEvent(BaseModel):
    type: str  # status / memory_card / text_chunk / action_buttons / error / done
    data: dict


def status_event(stage: str, label: str) -> SSEEvent:
    return SSEEvent(type="status", data={"stage": stage, "label": label})


def memory_card_event(summary: str, layer: str) -> SSEEvent | None:
    if not summary:
        return None
    return SSEEvent(type="memory_card", data={"summary": summary, "layer": layer})


def text_chunk_event(text: str) -> SSEEvent:
    return SSEEvent(type="text_chunk", data={"text": text})


def action_buttons_event(
    buttons: list[dict],
    prompt: str | None = None,
    candidate_summary: str | None = None,
) -> SSEEvent:
    data = {"buttons": buttons}
    if prompt:
        data["prompt"] = prompt
    if candidate_summary:
        data["candidate_summary"] = candidate_summary
    return SSEEvent(type="action_buttons", data=data)


def done_event() -> SSEEvent:
    return SSEEvent(type="done", data={})


def error_event(message: str) -> SSEEvent:
    return SSEEvent(type="error", data={"message": message})
