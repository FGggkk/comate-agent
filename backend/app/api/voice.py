"""Qwen Audio Realtime 的服务端代理入口。"""

import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.api.deps import get_current_user, get_user_id_from_token
from app.config.settings import get_settings
from app.db.session import async_session_factory
from app.graph.tools import TOOL_REGISTRY
from app.models.conversation import Message, Session
from app.services.soul_service import get_inventory
from app.services.tacit_profile_service import schedule_tacit_refresh

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
        "涉及天气、当前时间或需要检索的事实性问题时，优先调用已提供的工具获取结果，"
        "不要凭记忆猜测实时信息；缺少工具所需信息时先向用户追问。"
        "不要声称能够在现实世界中执行尚未完成的操作。"
    )


def _response_modalities(reply_mode: str) -> list[str]:
    return ["audio", "text"] if reply_mode == "audio" else ["text"]


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
            "modalities": ["text"],
            "voice": settings.qwen_audio_realtime_voice,
            "input_audio_format": "pcm",
            "output_audio_format": "pcm",
            "turn_detection": None,
            "instructions": _voice_instructions(soul),
            "tools": TOOL_REGISTRY.to_openai_tools(),
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


async def _proxy_browser_events(websocket: WebSocket, upstream, turn: dict) -> None:
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
            reply_mode = "audio" if payload.get("reply_mode") == "audio" else "text"
            transcription_only = bool(payload.get("transcription_only"))
            turn.update(
                user_transcript="",
                agent_transcript="",
                reply_mode=reply_mode,
                transcription_only=transcription_only,
                transcript_ready=False,
                saved=False,
                response_transcripts={},
                tool_response_ids=set(),
                handled_tool_call_ids=set(),
            )
            await upstream.send(json.dumps({"type": "input_audio_buffer.commit"}))
            if not transcription_only:
                await upstream.send(json.dumps({
                    "type": "response.create",
                    "response": {
                        "modalities": _response_modalities(reply_mode),
                    },
                }))
        elif event_type == "response.cancel":
            await upstream.send(json.dumps({"type": "response.cancel"}))
        elif event_type == "close":
            return
        else:
            await websocket.send_json({"type": "voice.error", "message": "不支持的语音事件"})


async def _persist_voice_turn(
    user_id: str,
    session_id: str,
    user_transcript: str,
    agent_transcript: str,
    soul: dict | None,
    reply_mode: str,
) -> dict | None:
    """只在一轮语音的最终文本齐全时，复用现有会话消息表保存。"""
    user_content = user_transcript.strip()
    agent_content = agent_transcript.strip()
    if not user_content or not agent_content:
        return None

    async with async_session_factory() as db:
        session_result = await db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == user_id)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            return None

        user_message = Message(
            session_id=session.id,
            role="user",
            content=user_content,
            metadata_=json.dumps({"source": "voice", "input": "audio"}, ensure_ascii=False),
        )
        agent_metadata = {"source": "voice", "output": reply_mode}
        if soul:
            agent_metadata["soul"] = soul
        agent_message = Message(
            session_id=session.id,
            role="agent",
            content=agent_content,
            metadata_=json.dumps(agent_metadata, ensure_ascii=False),
        )
        db.add_all([user_message, agent_message])

        if not session.title_auto_set and session.title == "新对话":
            session.title = user_content[:30] + ("..." if len(user_content) > 30 else "")
            session.title_auto_set = True
        session.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user_message)
        await db.refresh(agent_message)
        saved = {
            "session": {
                "id": str(session.id),
                "title": session.title,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            },
            "user": {"id": str(user_message.id)},
            "agent": {"id": str(agent_message.id)},
        }

    try:
        schedule_tacit_refresh(user_id, session_id)
    except Exception as exc:
        print(f"[voice] schedule tacit refresh failed: {exc}")
    return saved


async def _handle_tool_call(upstream, event: dict, turn: dict) -> None:
    """执行语音模型请求的工具，并让模型基于工具结果继续回复。"""
    call_id = event.get("call_id")
    if not isinstance(call_id, str) or not call_id:
        print("[voice] tool call ignored because call_id is missing")
        return

    handled_call_ids = turn.setdefault("handled_tool_call_ids", set())
    if call_id in handled_call_ids:
        return
    handled_call_ids.add(call_id)

    name = event.get("name")
    raw_arguments = event.get("arguments") or "{}"
    try:
        arguments = json.loads(raw_arguments)
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是 JSON 对象")
    except (json.JSONDecodeError, ValueError) as exc:
        output = {"error": f"工具参数无效：{exc}"}
    else:
        tool = TOOL_REGISTRY.get(name) if isinstance(name, str) else None
        if not tool:
            output = {"error": f"未注册的工具：{name or 'unknown'}"}
        else:
            try:
                result = await tool.execute(**arguments)
                output = {"result": result}
            except Exception as exc:
                print(f"[voice] tool {name} failed: {exc}")
                output = {"error": f"工具执行失败：{exc}"}

    response_id = event.get("response_id")
    if isinstance(response_id, str) and response_id:
        turn.setdefault("tool_response_ids", set()).add(response_id)

    await upstream.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(output, ensure_ascii=False),
        },
    }, ensure_ascii=False))
    await upstream.send(json.dumps({
        "type": "response.create",
        "response": {"modalities": _response_modalities(turn["reply_mode"])},
    }, ensure_ascii=False))


def _record_agent_transcript(turn: dict, event: dict, transcript: str, *, replace: bool) -> None:
    """按响应 ID 记录文本，工具调用前的中间响应不会污染最终持久化内容。"""
    response_id = event.get("response_id")
    if not isinstance(response_id, str) or not response_id:
        turn["agent_transcript"] = transcript if replace else turn["agent_transcript"] + transcript
        return

    transcripts = turn.setdefault("response_transcripts", {})
    transcripts[response_id] = transcript if replace else transcripts.get(response_id, "") + transcript


async def _proxy_model_events(
    websocket: WebSocket,
    upstream,
    user_id: str,
    session_id: str,
    soul: dict | None,
    turn: dict,
) -> None:
    async for raw_event in upstream:
        try:
            event = json.loads(raw_event)
        except json.JSONDecodeError:
            await websocket.send_text(raw_event)
            continue

        event_type = event.get("type")
        if event_type == "conversation.item.input_audio_transcription.delta":
            turn["user_transcript"] += event.get("delta") or event.get("text", "")
        elif event_type == "conversation.item.input_audio_transcription.completed":
            turn["user_transcript"] = event.get("transcript") or turn["user_transcript"]
        elif event_type in {"response.audio_transcript.delta", "response.text.delta"}:
            _record_agent_transcript(turn, event, event.get("delta") or event.get("text", ""), replace=False)
        elif event_type in {"response.audio_transcript.done", "response.text.done"}:
            _record_agent_transcript(
                turn,
                event,
                event.get("transcript") or event.get("text") or "",
                replace=bool(event.get("transcript") or event.get("text")),
            )

        await websocket.send_text(raw_event)

        if event_type == "conversation.item.input_audio_transcription.completed" and turn.get("transcription_only"):
            transcript = turn["user_transcript"].strip()
            if transcript:
                turn["transcript_ready"] = True
                await websocket.send_json({
                    "type": "voice.transcript_ready",
                    "data": {"text": transcript},
                })
            else:
                await websocket.send_json({"type": "voice.error", "message": "未识别到有效语音内容"})
            return

        if event_type == "response.function_call_arguments.done":
            await _handle_tool_call(upstream, event, turn)
            continue

        response_status = event.get("response", {}).get("status") or event.get("status")
        if event_type != "response.done" or turn["saved"] or response_status not in {None, "completed"}:
            continue
        response_id = event.get("response", {}).get("id") or event.get("response_id")
        if response_id in turn.get("tool_response_ids", set()):
            turn.get("response_transcripts", {}).pop(response_id, None)
            continue
        try:
            agent_transcript = turn.get("response_transcripts", {}).get(
                response_id, turn["agent_transcript"]
            )
            saved = await _persist_voice_turn(
                user_id,
                session_id,
                turn["user_transcript"],
                agent_transcript,
                soul,
                turn["reply_mode"],
            )
            if saved:
                turn["saved"] = True
                await websocket.send_json({"type": "voice.messages_saved", "data": saved})
        except Exception as exc:
            print(f"[voice] save voice turn failed: {exc}")
            await websocket.send_json({"type": "voice.error", "message": "语音消息保存失败"})


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

            turn = {
                "user_transcript": "",
                "agent_transcript": "",
                "reply_mode": "text",
                "transcription_only": False,
                "transcript_ready": False,
                "saved": False,
                "response_transcripts": {},
                "tool_response_ids": set(),
                "handled_tool_call_ids": set(),
            }
            browser_task = asyncio.create_task(_proxy_browser_events(websocket, upstream, turn))
            model_task = asyncio.create_task(
                _proxy_model_events(websocket, upstream, user_id, session_id, soul, turn)
            )
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
