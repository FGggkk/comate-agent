"""发布前检索验证的服务与接口契约测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin_company_knowledge
from app.api.admin_auth import get_current_admin
from app.db.session import get_db
from app.plugins.company_knowledge import service
from app.plugins.company_knowledge.retriever import RetrievedChunk


class CompanyKnowledgeValidationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_requires_retrieval_validation(self):
        source = SimpleNamespace(id="source-1", status="indexed")
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)))

        with patch.object(service, "_get_source", AsyncMock(return_value=source)):
            with self.assertRaisesRegex(service.CompanyKnowledgeServiceError, "检索验证"):
                await service.publish_company_source(db, "source-1", "admin-1")

    async def test_validation_transitions_indexed_chunk_set_to_validated(self):
        source = SimpleNamespace(id="source-1", status="indexed")
        chunk_set = SimpleNamespace(status="indexed", validated_by=None, validated_at=None)
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with (
            patch.object(service, "_get_source", AsyncMock(return_value=source)),
            patch.object(service, "_get_chunk_set", AsyncMock(return_value=chunk_set)),
        ):
            result = await service.validate_chunk_set(
                db, source_id="source-1", chunk_set_id="chunk-set-1", admin_id="admin-1"
            )

        self.assertIs(result, chunk_set)
        self.assertEqual(chunk_set.status, "validated")
        self.assertEqual(chunk_set.validated_by, "admin-1")
        self.assertIsNotNone(chunk_set.validated_at)
        self.assertEqual(source.status, "validated")
        db.commit.assert_awaited_once()

    async def test_publish_marks_active_chunk_set_as_published(self):
        source = SimpleNamespace(
            id="source-1",
            status="validated",
            title="测试制度",
            active_chunk_set_id=None,
            replaced_source_id=None,
            published_by=None,
            published_at=None,
        )
        chunk_set = SimpleNamespace(id="chunk-set-1", status="validated")
        validated_result = SimpleNamespace(scalar_one_or_none=lambda: chunk_set)
        previous_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[validated_result, previous_result]),
            get=AsyncMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        with patch.object(service, "_get_source", AsyncMock(return_value=source)):
            result = await service.publish_company_source(db, "source-1", "admin-1")

        self.assertIs(result, source)
        self.assertEqual(source.status, "published")
        self.assertEqual(source.active_chunk_set_id, "chunk-set-1")
        self.assertEqual(chunk_set.status, "published")

    async def test_validation_keeps_already_published_source_online(self):
        source = SimpleNamespace(id="source-1", status="published")
        chunk_set = SimpleNamespace(status="indexed", validated_by=None, validated_at=None)
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with (
            patch.object(service, "_get_source", AsyncMock(return_value=source)),
            patch.object(service, "_get_chunk_set", AsyncMock(return_value=chunk_set)),
        ):
            await service.validate_chunk_set(
                db, source_id="source-1", chunk_set_id="chunk-set-1", admin_id="admin-1"
            )

        self.assertEqual(chunk_set.status, "validated")
        self.assertEqual(source.status, "published")


class CompanyKnowledgeValidationApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(admin_company_knowledge.router)
        app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id="admin-1")
        app.dependency_overrides[get_db] = lambda: SimpleNamespace()
        self.client = TestClient(app)

    def test_preview_returns_similarity_and_expected_chunk_hit(self):
        chunk_set = SimpleNamespace(id="chunk-set-1", status="indexed")
        source_chunk = SimpleNamespace(id="chunk-1")
        preview = RetrievedChunk(
            chunk_id="chunk-1",
            chunk_set_id="chunk-set-1",
            source_id="source-1",
            title="测试制度",
            version="V1.0",
            effective_at="2026-08-04",
            section_path="考勤 / 年假",
            content="员工应提前提交年假申请。",
            similarity=0.92,
        )

        async def fake_detail(*args, **kwargs):
            return SimpleNamespace(), [chunk_set], [source_chunk]

        async def fake_preview(*args, **kwargs):
            return [preview]

        with (
            patch.object(admin_company_knowledge, "get_company_source_detail", fake_detail),
            patch.object(admin_company_knowledge, "preview_company_knowledge_chunk_set", fake_preview),
        ):
            response = self.client.post(
                "/api/admin/company-knowledge/sources/source-1/chunk-sets/chunk-set-1/retrieval-preview",
                json={
                    "question": "年假怎么申请？",
                    "top_k": 3,
                    "expected_chunk_ids": ["chunk-1"],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["expected_hit"])
        self.assertEqual(payload["data"]["items"][0]["similarity"], 0.92)
        self.assertTrue(payload["data"]["items"][0]["meets_minimum_similarity"])

    def test_validate_rejects_a_query_without_qualified_results(self):
        chunk_set = SimpleNamespace(id="chunk-set-1", status="indexed")
        source_chunk = SimpleNamespace(id="chunk-1")

        async def fake_detail(*args, **kwargs):
            return SimpleNamespace(), [chunk_set], [source_chunk]

        async def fake_preview(*args, **kwargs):
            return []

        with (
            patch.object(admin_company_knowledge, "get_company_source_detail", fake_detail),
            patch.object(admin_company_knowledge, "preview_company_knowledge_chunk_set", fake_preview),
        ):
            response = self.client.post(
                "/api/admin/company-knowledge/sources/source-1/chunk-sets/chunk-set-1/validate",
                json={"question": "年假怎么申请？"},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["success"])
        self.assertIn("最低相似度", payload["message"])


if __name__ == "__main__":
    unittest.main()
