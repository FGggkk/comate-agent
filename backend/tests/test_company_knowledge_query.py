"""公司制度问答 SSE 链路测试，使用内存替身避免触发真实数据库和模型。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import company_knowledge
from app.api.deps import get_current_user
from app.db.session import get_db
from app.plugins.company_knowledge.retriever import RetrievedChunk


class CompanyKnowledgeQueryTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(company_knowledge.router)
        app.dependency_overrides[get_current_user] = lambda: "test-user"
        app.dependency_overrides[get_db] = lambda: SimpleNamespace()
        self.client = TestClient(app)

    def test_streams_sources_and_persists_citation_snapshot(self):
        saved = {}
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            source_id="source-1",
            title="员工休假制度",
            version="V1.2",
            effective_at="2026-01-01",
            section_path="休假 / 年假",
            content="员工应提前三个工作日提交年假申请。",
            similarity=0.92,
        )

        async def fake_session(*args, **kwargs):
            return SimpleNamespace(id="session-1")

        async def fake_save_user(*args, **kwargs):
            return SimpleNamespace(id="user-message-1")

        async def fake_retrieve(*args, **kwargs):
            return [chunk]

        async def fake_stream(*args, **kwargs):
            yield "年假应提前三个工作日申请。"

        async def fake_save_answer(*args, **kwargs):
            saved.update(kwargs)
            return SimpleNamespace(id="agent-message-1")

        with (
            patch.object(company_knowledge, "ensure_company_knowledge_session", fake_session),
            patch.object(company_knowledge, "save_company_knowledge_user_message", fake_save_user),
            patch.object(company_knowledge, "retrieve_company_knowledge", fake_retrieve),
            patch.object(company_knowledge, "stream_company_knowledge_answer", fake_stream),
            patch.object(company_knowledge, "save_company_knowledge_answer", fake_save_answer),
            patch.object(company_knowledge, "schedule_tacit_refresh"),
        ):
            response = self.client.post(
                "/api/company-knowledge/query",
                json={"message": "年假怎么申请？", "knowledge_type": "policy", "input_mode": "voice"},
            )

        self.assertEqual(response.status_code, 200)
        events = _events(response.text)
        self.assertEqual(events[0]["type"], "message_saved")
        self.assertEqual(events[1]["type"], "sources")
        self.assertEqual(events[1]["data"]["items"][0]["title"], "员工休假制度")
        self.assertIn("提前三个工作日", events[2]["data"]["text"])
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(saved["citations"][0]["source_id"], "source-1")
        self.assertEqual(saved["question"], "年假怎么申请？")

    def test_returns_refusal_without_calling_chat_model_when_no_evidence(self):
        saved = {}

        async def fake_session(*args, **kwargs):
            return SimpleNamespace(id="session-1")

        async def fake_save_user(*args, **kwargs):
            return SimpleNamespace(id="user-message-1")

        async def fake_retrieve(*args, **kwargs):
            return []

        async def fake_save_answer(*args, **kwargs):
            saved.update(kwargs)
            return SimpleNamespace(id="agent-message-1")

        with (
            patch.object(company_knowledge, "ensure_company_knowledge_session", fake_session),
            patch.object(company_knowledge, "save_company_knowledge_user_message", fake_save_user),
            patch.object(company_knowledge, "retrieve_company_knowledge", fake_retrieve),
            patch.object(company_knowledge, "stream_company_knowledge_answer") as answer_stream,
            patch.object(company_knowledge, "save_company_knowledge_answer", fake_save_answer),
            patch.object(company_knowledge, "schedule_tacit_refresh"),
        ):
            response = self.client.post(
                "/api/company-knowledge/query",
                json={"message": "没有覆盖的问题怎么办？"},
            )

        events = _events(response.text)
        self.assertFalse(any(event["type"] == "sources" for event in events))
        self.assertEqual(events[1]["data"]["text"], "当前已发布制度中未找到可引用依据。")
        self.assertFalse(answer_stream.called)
        self.assertEqual(saved["citations"], [])


def _events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


if __name__ == "__main__":
    unittest.main()
