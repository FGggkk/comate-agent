"""发布前检索验证的服务与接口契约测试。"""

import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin_company_knowledge
from app.api.admin_auth import get_current_admin
from app.db.session import get_db
from app.plugins.company_knowledge import service
from app.plugins.company_knowledge import retriever
from app.plugins.company_knowledge.retriever import RetrievedChunk


class CompanyKnowledgeValidationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_answer_validation_compares_generated_answer_with_all_chunks(self):
        source = SimpleNamespace(id="source-1", title="测试制度", version="V1.0")
        chunk_set = SimpleNamespace(id="chunk-set-1", status="indexed")
        chunk = SimpleNamespace(
            id="chunk-1",
            chunk_index=0,
            section_path="年假",
            content="员工应提前提交年假申请。",
            embedding=[1.0, 0.0],
        )
        other_chunk = SimpleNamespace(
            id="chunk-2",
            chunk_index=1,
            section_path="考勤",
            content="员工应按时打卡。",
            embedding=[0.0, 1.0],
        )
        match = RetrievedChunk(
            chunk_id="chunk-1",
            chunk_set_id="chunk-set-1",
            source_id="source-1",
            title="测试制度",
            version="V1.0",
            effective_at="2026-08-04",
            section_path="年假",
            content="员工应提前提交年假申请。",
            similarity=0.92,
        )
        run = SimpleNamespace(
            id="run-1",
            source_id="source-1",
            chunk_set_id="chunk-set-1",
            question="年假如何申请？",
            expected_chunk_ids=["chunk-1"],
            top_k=2,
            status="running",
            answer="",
            answer_similarity=None,
            correctness_score=None,
            faithfulness_score=None,
            evaluation_verdict="pending",
            evaluation_reason="",
            retrieval_snapshot={},
            error_message="",
            completed_at=None,
        )
        db = SimpleNamespace(get=AsyncMock(return_value=run), commit=AsyncMock(), refresh=AsyncMock())

        with (
            patch.object(service, "_load_validation_context", AsyncMock(return_value=(source, chunk_set, [chunk, other_chunk]))),
            patch.object(service, "preview_company_knowledge_chunk_set", AsyncMock(return_value=[match])),
            patch.object(service, "get_embedding", AsyncMock(side_effect=[[1.0, 0.0], [1.0, 0.0]])),
            patch.object(service, "generate_company_knowledge_answer", AsyncMock(return_value="员工应提前提交年假申请。")),
            patch.object(
                service,
                "_evaluate_company_knowledge_answer",
                AsyncMock(
                    return_value={
                        "correctness_score": 0.96,
                        "faithfulness_score": 0.98,
                        "verdict": "pass",
                        "reason": "回答与预期证据一致。",
                    }
                ),
            ),
        ):
            run = await service.execute_company_knowledge_validation_run(
                db,
                run_id="run-1",
            )

        self.assertEqual(run.status, "succeeded")
        self.assertEqual(run.question, "年假如何申请？")
        self.assertEqual(run.expected_chunk_ids, ["chunk-1"])
        self.assertEqual(run.answer, "员工应提前提交年假申请。")
        self.assertEqual(run.answer_similarity, 1.0)
        self.assertEqual(run.evaluation_verdict, "pass")
        self.assertTrue(run.retrieval_snapshot["expected_hit"])
        self.assertTrue(run.retrieval_snapshot["expected_qualified"])
        self.assertEqual(run.retrieval_snapshot["answer_match"]["total_chunks"], 2)
        self.assertEqual(run.retrieval_snapshot["answer_match"]["expected_rank"], 1)
        self.assertTrue(run.retrieval_snapshot["answer_match"]["expected_is_top"])
        self.assertTrue(run.retrieval_snapshot["can_confirm"])
        db.commit.assert_awaited_once()

    async def test_manual_answer_validation_requires_selected_chunk(self):
        source = SimpleNamespace(id="source-1", title="测试制度", version="V1.0")
        chunk_set = SimpleNamespace(id="chunk-set-1", status="indexed")
        chunk = SimpleNamespace(
            id="chunk-1",
            chunk_index=0,
            section_path="年假",
            content="员工应提前提交年假申请。",
            embedding=[1.0, 0.0],
        )
        db = SimpleNamespace(add=Mock(), flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())

        with patch.object(service, "_load_validation_context", AsyncMock(return_value=(source, chunk_set, [chunk]))):
            with self.assertRaisesRegex(service.CompanyKnowledgeServiceError, "请选择需要验证的切分段"):
                await service.create_company_knowledge_validation_run(
                    db,
                    source_id="source-1",
                    chunk_set_id="chunk-set-1",
                    question="年假如何申请？",
                    expected_chunk_id="",
                    admin_id="admin-1",
                )

    async def test_manual_answer_validation_reuses_running_task_for_same_chunk_set(self):
        source = SimpleNamespace(id="source-1", title="测试制度", version="V1.0")
        chunk_set = SimpleNamespace(id="chunk-set-1", source_id="source-1", status="indexed")
        chunk = SimpleNamespace(id="chunk-1", chunk_index=0, section_path="年假", content="员工应提前提交年假申请。")
        running_run = SimpleNamespace(id="run-1", status="running")

        with (
            patch.object(service, "_load_validation_context", AsyncMock(return_value=(source, chunk_set, [chunk]))),
            patch.object(service, "_expire_stale_validation_runs", AsyncMock(return_value=0)),
            patch.object(service, "_get_active_validation_run", AsyncMock(return_value=running_run)),
        ):
            run = await service.create_company_knowledge_validation_run(
                SimpleNamespace(),
                source_id="source-1",
                chunk_set_id="chunk-set-1",
                question="年假如何申请？",
                expected_chunk_id="chunk-1",
                admin_id="admin-1",
            )

        self.assertIs(run, running_run)
        self.assertFalse(run._starts_background_task)

    async def test_manual_answer_validation_timeout_marks_task_failed(self):
        run = SimpleNamespace(id="run-1", status="running", error_message="", completed_at=None)
        db = SimpleNamespace(
            get=AsyncMock(side_effect=[run, run]),
            rollback=AsyncMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        async def never_finish(*args, **kwargs):
            await asyncio.Future()

        with (
            patch.object(service, "VALIDATION_RUN_TIMEOUT_SECONDS", 0.01),
            patch.object(service, "_run_company_knowledge_validation_pipeline", never_finish),
        ):
            result = await service.execute_company_knowledge_validation_run(db, run_id="run-1")

        self.assertEqual(result.status, "failed")
        self.assertIn("超过 0.01 秒", result.error_message)
        db.rollback.assert_awaited_once()

    async def test_only_a_passing_answer_validation_run_can_confirm_chunk_set(self):
        source = SimpleNamespace(id="source-1", status="indexed")
        chunk_set = SimpleNamespace(id="chunk-set-1", status="indexed")
        run = SimpleNamespace(
            id="run-1",
            source_id="source-1",
            chunk_set_id="chunk-set-1",
            status="succeeded",
            expected_chunk_ids=["chunk-1"],
            retrieval_snapshot={
                "question_match": {"expected_is_top": True},
                "answer_match": {"expected_is_top": True},
            },
            evaluation_verdict="pass",
            confirmed_by=None,
            confirmed_at=None,
        )
        db = SimpleNamespace(get=AsyncMock(return_value=run), refresh=AsyncMock())
        validated_set = SimpleNamespace(id="chunk-set-1", status="validated")

        with (
            patch.object(service, "_get_source", AsyncMock(return_value=source)),
            patch.object(service, "_get_chunk_set", AsyncMock(return_value=chunk_set)),
            patch.object(service, "validate_chunk_set", AsyncMock(return_value=validated_set)) as validate,
        ):
            result_run, result_chunk_set = await service.confirm_company_knowledge_validation_run(
                db,
                source_id="source-1",
                chunk_set_id="chunk-set-1",
                run_id="run-1",
                admin_id="admin-1",
            )

        self.assertIs(result_run, run)
        self.assertIs(result_chunk_set, validated_set)
        self.assertEqual(run.status, "confirmed")
        validate.assert_awaited_once()

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

    async def test_publish_restores_archived_source_with_published_chunk_set(self):
        source = SimpleNamespace(
            id="source-1",
            status="archived",
            title="测试制度",
            active_chunk_set_id=None,
            replaced_source_id=None,
            published_by=None,
            published_at=None,
        )
        chunk_set = SimpleNamespace(id="chunk-set-1", status="published")
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

    async def test_publish_restore_archived_source_rejects_when_same_title_published(self):
        source = SimpleNamespace(
            id="source-1",
            status="archived",
            title="测试制度",
            active_chunk_set_id=None,
            replaced_source_id=None,
            published_by=None,
            published_at=None,
        )
        chunk_set = SimpleNamespace(id="chunk-set-1", status="published")
        validated_result = SimpleNamespace(scalar_one_or_none=lambda: chunk_set)
        other_source = SimpleNamespace(id="source-2", status="published")
        previous_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [other_source]))
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[validated_result, previous_result]),
            get=AsyncMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        with patch.object(service, "_get_source", AsyncMock(return_value=source)):
            with self.assertRaisesRegex(service.CompanyKnowledgeServiceError, "同名已发布版本"):
                await service.publish_company_source(db, "source-1", "admin-1")

        self.assertEqual(source.status, "archived")

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

    async def test_delete_archived_source_clears_replaced_source_references(self):
        source = SimpleNamespace(id="source-1", status="archived")
        db = SimpleNamespace(
            execute=AsyncMock(),
            delete=AsyncMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        with patch.object(service, "_get_source", AsyncMock(return_value=source)):
            await service.delete_archived_company_source(db, "source-1")

        db.execute.assert_awaited_once()
        update_stmt = db.execute.await_args.args[0]
        statement_text = str(update_stmt)
        self.assertIn("replaced_source_id", statement_text)
        db.delete.assert_awaited_once_with(source)
        db.commit.assert_awaited_once()

    async def test_delete_archived_source_rejects_non_archived(self):
        source = SimpleNamespace(id="source-1", status="published")
        db = SimpleNamespace(execute=AsyncMock(), delete=AsyncMock(), commit=AsyncMock())

        with patch.object(service, "_get_source", AsyncMock(return_value=source)):
            with self.assertRaisesRegex(service.CompanyKnowledgeServiceError, "只能删除已下架"):
                await service.delete_archived_company_source(db, "source-1")

        db.delete.assert_not_awaited()
        db.commit.assert_not_awaited()


class CompanyKnowledgeRetrieverTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_query_includes_near_threshold_published_active_chunk_set(self):
        row = {
            "chunk_id": "chunk-1",
            "chunk_set_id": "chunk-set-1",
            "source_id": "source-1",
            "title": "公司文化",
            "version": "1.0",
            "effective_at": datetime(2026, 8, 4, tzinfo=timezone.utc),
            "section_path": "公司文化",
            "content": "公司名称为伴行。",
            "similarity": 0.345,
        }
        result = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [row]))
        db = SimpleNamespace(execute=AsyncMock(return_value=result))

        with patch.object(retriever, "get_embedding", AsyncMock(return_value=[0.1, 0.2])):
            chunks = await retriever.retrieve_company_knowledge(
                "我们公司叫什么名字？", "policy", db, top_k=3
            )

        statement = str(db.execute.await_args.args[0])
        self.assertIn("chunk_set.status IN ('indexed', 'validated', 'published')", statement)
        self.assertEqual([chunk.chunk_id for chunk in chunks], ["chunk-1"])
        self.assertLess(chunks[0].similarity, retriever.MIN_SIMILARITY)
        self.assertGreaterEqual(chunks[0].similarity, retriever.MIN_USER_QUERY_SIMILARITY)


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

    def test_answer_validation_run_endpoint_returns_persisted_run(self):
        run = SimpleNamespace(
            id="run-1",
            source_id="source-1",
            chunk_set_id="chunk-set-1",
            mode="manual",
            question="年假如何申请？",
            expected_chunk_ids=["chunk-1"],
            top_k=3,
            retrieval_snapshot={"expected_hit": True, "can_confirm": True},
            answer="员工应提前提交年假申请。",
            answer_similarity=0.91,
            correctness_score=0.95,
            faithfulness_score=0.97,
            evaluation_verdict="pass",
            evaluation_reason="回答有资料依据。",
            status="succeeded",
            error_message="",
            created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            completed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            confirmed_at=None,
        )

        async def fake_create(*args, **kwargs):
            return run

        with (
            patch.object(admin_company_knowledge, "create_company_knowledge_validation_run", fake_create),
            patch.object(admin_company_knowledge, "_execute_validation_run_in_background", AsyncMock()),
        ):
            response = self.client.post(
                "/api/admin/company-knowledge/sources/source-1/chunk-sets/chunk-set-1/validation-runs",
                json={
                    "question": "年假如何申请？",
                    "expected_chunk_id": "chunk-1",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["run"]["answer"], "员工应提前提交年假申请。")
        self.assertEqual(payload["data"]["run"]["evaluation_verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
