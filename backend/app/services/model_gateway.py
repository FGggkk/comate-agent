import json

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.model import get_model_config


class ModelGateway:
    def __init__(self):
        cfg = get_model_config()
        self.api_key = cfg.api_key
        self.base_url = cfg.base_url
        self.model = cfg.model
        self.max_tokens = cfg.max_tokens
        self.temperature = cfg.temperature

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
    async def chat(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def stream(self, prompt: str, system: str = ""):
        """异步生成器，逐 token 产出文本（仅正文增量）"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async for _, content, _ in self._stream_messages(messages):
            if content:
                yield content

    async def chat_with_tools(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        """非流式调用，支持 tools。返回完整 response dict"""
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def stream_messages(self, messages: list[dict]):
        """从完整的 messages 数组流式生成（仅正文增量）"""
        async for _, content, _ in self._stream_messages(messages):
            if content:
                yield content

    async def stream_messages_full(self, messages: list[dict], tools: list[dict] | None = None):
        """流式生成，yield (reasoning, content, tool_calls)；支持 tools 与 reasoning_content"""
        async for item in self._stream_messages(messages, tools=tools):
            yield item

    async def _stream_messages(self, messages: list[dict], tools: list[dict] | None = None):
        """内部方法：流式生成。逐 chunk 产出 (reasoning, content, tool_calls_parts)"""
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            reasoning = delta.get("reasoning_content") or ""
                            content = delta.get("content") or ""
                            tool_calls = delta.get("tool_calls") or []
                            if reasoning or content or tool_calls:
                                yield reasoning, content, tool_calls
                        except json.JSONDecodeError:
                            continue


gateway = ModelGateway()
