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


def action_buttons_event(buttons: list[dict]) -> SSEEvent:
    return SSEEvent(type="action_buttons", data={"buttons": buttons})


def done_event() -> SSEEvent:
    return SSEEvent(type="done", data={})


def error_event(message: str) -> SSEEvent:
    return SSEEvent(type="error", data={"message": message})
