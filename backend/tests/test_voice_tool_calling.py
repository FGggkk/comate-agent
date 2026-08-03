"""语音工具调用的回归测试。"""

import json
import unittest

from app.api import voice
from app.graph.tools import TOOL_REGISTRY


class FakeUpstream:
    """记录代理发往模型的事件，并按预设顺序回放模型事件。"""

    def __init__(self, events=None):
        self.events = events or []
        self.sent = []

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self._iterate_events()

    async def _iterate_events(self):
        for event in self.events:
            yield json.dumps(event, ensure_ascii=False)


class FakeBrowser:
    def __init__(self):
        self.text_events = []
        self.json_events = []

    async def send_text(self, message):
        self.text_events.append(json.loads(message))

    async def send_json(self, event):
        self.json_events.append(event)


class FakeWeatherTool:
    name = "get_weather"
    description = "查询天气"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        if kwargs != {"city": "北京"}:
            raise ValueError("unexpected weather arguments")
        return "北京：晴，25°C"


class VoiceToolCallingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_weather = TOOL_REGISTRY.get("get_weather")
        self.original_persist = voice._persist_voice_turn
        TOOL_REGISTRY._tools["get_weather"] = FakeWeatherTool()
        self.persisted = []

        async def fake_persist(*args):
            self.persisted.append(args)
            return {
                "session": {"id": "session-1", "title": "天气", "updated_at": None},
                "user": {"id": "user-message"},
                "agent": {"id": "agent-message"},
            }

        voice._persist_voice_turn = fake_persist

    def tearDown(self):
        if self.original_weather is None:
            TOOL_REGISTRY._tools.pop("get_weather", None)
        else:
            TOOL_REGISTRY._tools["get_weather"] = self.original_weather
        voice._persist_voice_turn = self.original_persist

    @staticmethod
    def make_turn(reply_mode="text"):
        return {
            "user_transcript": "北京天气怎么样",
            "agent_transcript": "",
            "reply_mode": reply_mode,
            "saved": False,
            "response_transcripts": {},
            "tool_response_ids": set(),
            "handled_tool_call_ids": set(),
        }

    async def test_session_registers_existing_tools(self):
        upstream = FakeUpstream()

        await voice._send_context(upstream, None, [])

        session = upstream.sent[0]["session"]
        tool_names = {tool["function"]["name"] for tool in session["tools"]}
        self.assertTrue({"get_weather", "get_current_time", "search_web"} <= tool_names)

    async def test_tool_call_waits_for_final_response_before_persisting(self):
        tool_response_id = "response-tool"
        final_response_id = "response-final"
        upstream = FakeUpstream([
            {
                "type": "response.function_call_arguments.done",
                "response_id": tool_response_id,
                "call_id": "call-weather",
                "name": "get_weather",
                "arguments": '{"city":"北京"}',
            },
            {
                "type": "response.done",
                "response": {"id": tool_response_id, "status": "completed"},
            },
            {
                "type": "response.text.delta",
                "response_id": final_response_id,
                "delta": "北京今天晴",
            },
            {
                "type": "response.text.done",
                "response_id": final_response_id,
                "text": "北京今天晴，适合出门。",
            },
            {
                "type": "response.done",
                "response": {"id": final_response_id, "status": "completed"},
            },
        ])
        browser = FakeBrowser()
        turn = self.make_turn()

        await voice._proxy_model_events(
            browser, upstream, "user-1", "session-1", None, turn
        )

        self.assertEqual(upstream.sent[0]["type"], "conversation.item.create")
        output = json.loads(upstream.sent[0]["item"]["output"])
        self.assertEqual(output["result"], "北京：晴，25°C")
        self.assertEqual(upstream.sent[1]["type"], "response.create")
        self.assertEqual(upstream.sent[1]["response"]["modalities"], ["text"])
        self.assertEqual(len(self.persisted), 1)
        self.assertEqual(self.persisted[0][3], "北京今天晴，适合出门。")
        self.assertTrue(turn["saved"])
        self.assertEqual(browser.json_events[-1]["type"], "voice.messages_saved")

    async def test_audio_reply_mode_is_preserved_after_tool_call(self):
        upstream = FakeUpstream()
        turn = self.make_turn(reply_mode="audio")
        event = {
            "type": "response.function_call_arguments.done",
            "response_id": "response-tool",
            "call_id": "call-weather",
            "name": "get_weather",
            "arguments": '{"city":"北京"}',
        }

        await voice._handle_tool_call(upstream, event, turn)

        self.assertEqual(upstream.sent[1]["response"]["modalities"], ["audio", "text"])

    async def test_unknown_tool_returns_error_and_keeps_response_flowing(self):
        upstream = FakeUpstream()
        turn = self.make_turn()
        event = {
            "type": "response.function_call_arguments.done",
            "response_id": "response-tool",
            "call_id": "call-unknown",
            "name": "unknown_tool",
            "arguments": "{}",
        }

        await voice._handle_tool_call(upstream, event, turn)

        output = json.loads(upstream.sent[0]["item"]["output"])
        self.assertIn("未注册的工具", output["error"])
        self.assertEqual(upstream.sent[1]["type"], "response.create")


if __name__ == "__main__":
    unittest.main()
