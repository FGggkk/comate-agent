"""公司知识库第一阶段的类型与边界契约测试。"""

import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin_company_knowledge, company_knowledge
from app.api.admin_auth import get_current_admin
from app.api.deps import get_current_user
from app.db.session import MIGRATION_SQL
from app.plugins.company_knowledge.memory_boundary import profile_safe_messages
from app.plugins.company_knowledge.registry import list_knowledge_types
from app.plugins.company_knowledge.schemas import CompanyKnowledgeQueryRequest


class CompanyKnowledgeContractTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(company_knowledge.router)
        app.include_router(admin_company_knowledge.router)
        app.dependency_overrides[get_current_user] = lambda: "test-user"
        app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id="admin-1")
        self.client = TestClient(app)

    def test_registry_keeps_all_future_types_but_only_policy_is_enabled(self):
        items = {item["key"]: item for item in list_knowledge_types()}

        self.assertEqual(set(items), {"policy", "faq", "history", "news", "department_knowledge"})
        self.assertTrue(items["policy"]["import_enabled"])
        self.assertTrue(items["policy"]["query_enabled"])
        self.assertTrue(items["policy"]["user_visible"])
        for key in ("faq", "history", "news", "department_knowledge"):
            self.assertFalse(items[key]["import_enabled"])
            self.assertFalse(items[key]["query_enabled"])
            self.assertFalse(items[key]["user_visible"])

    def test_user_and_admin_type_interfaces_share_the_same_contract(self):
        user_response = self.client.get("/api/company-knowledge/types")
        admin_response = self.client.get("/api/admin/company-knowledge/types")

        self.assertEqual(user_response.status_code, 200)
        self.assertEqual(admin_response.status_code, 200)
        self.assertTrue(user_response.json()["success"])
        self.assertEqual(user_response.json()["data"], admin_response.json()["data"])

    def test_disabled_type_returns_a_clear_query_contract_response(self):
        response = self.client.post(
            "/api/company-knowledge/query",
            json={"message": "公司的常见问题有哪些？", "knowledge_type": "faq"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["data"]["code"], "knowledge_type_disabled")

    def test_policy_query_contract_accepts_voice_transcript(self):
        request = CompanyKnowledgeQueryRequest(
            message="年假如何计算？",
            knowledge_type="policy",
            input_mode="voice",
        )

        self.assertEqual(request.knowledge_type, "policy")
        self.assertEqual(request.input_mode, "voice")

    def test_company_knowledge_messages_do_not_enter_persona_signal_input(self):
        messages = [
            SimpleNamespace(msg_type="text", content="我下周要申请婚假"),
            SimpleNamespace(msg_type="company_knowledge", content="婚假制度为十五天"),
        ]

        filtered = profile_safe_messages(messages)

        self.assertEqual(filtered, [messages[0]])

    def test_migration_declares_company_knowledge_tables_and_vector_index(self):
        migration_sql = "\n".join(MIGRATION_SQL)

        self.assertIn("CREATE TABLE IF NOT EXISTS company_knowledge_sources", migration_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS company_knowledge_chunks", migration_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS company_knowledge_jobs", migration_sql)
        self.assertIn("idx_company_knowledge_chunks_embedding_hnsw", migration_sql)


if __name__ == "__main__":
    unittest.main()
