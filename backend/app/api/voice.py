"""Qwen Audio Realtime 的服务端代理入口。"""

import asyncio
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.api.deps import get_current_user, get_user_id_from_token
from app.config.settings import get_settings
from app.db.session import async_session_factory
from app.models.conversation import Message, Session
from app.services.soul_service import get_inventory

router = APIRouter(prefix="/api/voice", tags=["voice"])
settings = get_settings()

INPUT_AUDIO = {"format": "pcm16", "sample_rate": 16000, "channels": 1}
OUTPUT_AUDIO = {"format": "pcm16", "sample_rate": 24000, "channels": 1}
CLIENT_PROTOCOL = "comate-auth"


def _is_configured() -> bool:
    return bool(
        settings.voice_enabled
        and settings.dashscope_api_key
        and settings.dashscope_workspace_id
        and settings.qwen_audio_realtime_url
    )


def _upstream_url() -> str:
    base_url = settings.qwen_audio_realtime_url.replace(
        "{workspace_id}", settings.dashscope_workspace_id
    )
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = settings.qwen_audio_realtime_model
    return urlunsplit(parts._replace(query=urlencode(query)))


def _token_from_subprotocols(websocket: WebSocket) -> str:
    """从 WebSocket 子协议取得 JWT，避免把令牌暴露在 URL 查询参数中。"""
    protocols = websocket.scope.get("subprotocols") or []
    if len(protocols) >= 2 and protocols[0] == CLIENT_PROTOCOL:
        return protocols[1]
    raise HTTPException(status_code=401, detail="缺少语音鉴权令牌")


def _voice_instructions(soul: dict | None) -> str:
    style = soul.get("name") if soul else "温柔陪伴型"
    return (
        "你是伴行，一位中文 AI 情感陪伴助手。"
        f"当前陪伴风格是「{style}」。"
        "请自然、温和地用中文交流；回答简洁，适合语音播放。"
        "不要声称能够在现实世界中执行尚未完成的操作。"
    )


async def _load_context(user_id: str, session_id: str) -> tuple[dict | None, list[Message]]:
    """验证会话归属，并读取有限的既有文本上下文。"""
    async with async_session_factory() as db:
        session_result = await db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == user_id)
        )
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="会话不存在")

        messages_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(settings.qwen_audio_realtime_max_history_turns * 2)
        )
        messages = list(reversed(messages_result.scalars().all()))

        try:
            inventory = await get_inventory(user_id, db)
            soul = inventory.get("current")
        except Exception as exc:
            print(f"[voice] load soul snapshot failed: {exc}")
            soul = None
        return soul, messages


async def _send_context(upstream, soul: dict | None, messages: list[Message]) -> None:
    await upstream.send(json.dumps({
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": settings.qwen_audio_realtime_voice,
            "input_audio_format": "pcm",
            "output_audio_format": "pcm",
            "turn_detection": None,
            "instructions": _voice_instructions(soul),
            "max_history_turns": settings.qwen_audio_realtime_max_history_turns,
        },
    }, ensure_ascii=False))

    for message in messages:
        role = "assistant" if message.role == "agent" else "user"
        await upstream.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": role,
                "content": [{"type": "input_text", "text": message.content}],
            },
        }, ensure_ascii=False))


async def _proxy_browser_events(websocket: WebSocket, upstream) -> None:
    """仅转换客户端需要的三类事件，防止前端任意修改模型会话配置。"""
    while True:
        payload = await websocket.receive_json()
        event_type = payload.get("type")
        if event_type == "audio.append":
            audio = payload.get("audio")
            if not isinstance(audio, str) or not audio:
                await websocket.send_json({"type": "voice.error", "message": "音频数据无效"})
                continue
            await upstream.send(json.dumps({"type": "input_audio_buffer.append", "audio": audio}))
        elif event_type == "audio.commit":
            await upstream.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await upstream.send(json.dumps({"type": "response.create"}))
        elif event_type == "response.cancel":
            await upstream.send(json.dumps({"type": "response.cancel"}))
        elif event_type == "close":
            return
        else:
            await websocket.send_json({"type": "voice.error", "message": "不支持的语音事件"})


async def _proxy_model_events(websocket: WebSocket, upstream) -> None:
    async for raw_event in upstream:
        await websocket.send_text(raw_event)


@router.get("/status")
async def voice_status(user_id: str = Depends(get_current_user)):
    """供前端判断语音入口是否可用，不返回任何密钥。"""
    return {
        "enabled": settings.voice_enabled,
        "configured": _is_configured(),
        "model": settings.qwen_audio_realtime_model,
        "mode": "push_to_talk",
        "input_audio": INPUT_AUDIO,
        "output_audio": OUTPUT_AUDIO,
    }


@router.websocket("/realtime")
async def voice_realtime(websocket: WebSocket, session_id: str):
    """将已鉴权的浏览器语音事件代理到 Qwen Realtime。"""
    try:
        user_id = get_user_id_from_token(_token_from_subprotocols(websocket))
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept(subprotocol=CLIENT_PROTOCOL)
    if not _is_configured():
        await websocket.send_json({
            "type": "voice.error",
            "message": "语音服务尚未配置，请检查 VOICE_ENABLED、DASHSCOPE_API_KEY 和 DASHSCOPE_WORKSPACE_ID。",
        })
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    try:
        soul, messages = await _load_context(user_id, session_id)
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "X-DashScope-WorkSpace": settings.dashscope_workspace_id,
            "User-Agent": "comate-agent/voice-proxy",
        }
        async with websockets.connect(
            _upstream_url(), additional_headers=headers, open_timeout=15
        ) as upstream:
            await _send_context(upstream, soul, messages)
            await websocket.send_json({"type": "voice.ready"})

            browser_task = asyncio.create_task(_proxy_browser_events(websocket, upstream))
            model_task = asyncio.create_task(_proxy_model_events(websocket, upstream))
            done, pending = await asyncio.wait(
                {browser_task, model_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
    except WebSocketDisconnect:
        return
    except HTTPException as exc:
        await websocket.send_json({"type": "voice.error", "message": exc.detail})
    except Exception as exc:
        print(f"[voice] realtime proxy failed: {exc}")
        try:
            await websocket.send_json({"type": "voice.error", "message": "语音服务连接失败"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
