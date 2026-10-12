"""B1 文档级关系图谱：纯逻辑测试（不依赖数据库）。"""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.plugins.company_knowledge.graph_service import (
    GraphServiceError,
    _system_supersede_edge,
    enqueue_graph_relation_extraction,
    enqueue_graph_relation_extractions_for_published_sources,
    execute_graph_relation_extraction_job,
    graph_extraction_job_to_dict,
    get_confirmed_relations,
    list_graph_relation_extraction_jobs,
    relation_to_dict,
    validate_relation_input,
)


class RelationValidationTests(unittest.TestCase):
    def test_accepts_valid_input(self):
        validate_relation_input(
            source_id="a",
            target_source_id="b",
            relation_type="cite",
            direction="directed",
            origin="llm",
        )

    def test_rejects_same_source_and_target(self):
        with self.assertRaises(GraphServiceError):
            validate_relation_input(
                source_id="a", target_source_id="a", relation_type="cite"
            )

    def test_rejects_unknown_relation_type(self):
        with self.assertRaises(GraphServiceError):
            validate_relation_input(
                source_id="a", target_source_id="b", relation_type="friendship"
            )

    def test_rejects_unknown_direction_and_origin(self):
        with self.assertRaises(GraphServiceError):
            validate_relation_input(
                source_id="a", target_source_id="b", relation_type="cite", direction="sideways"
            )
        with self.assertRaises(GraphServiceError):
            validate_relation_input(
                source_id="a", target_source_id="b", relation_type="cite", origin="guessed"
            )

    def test_rejects_missing_ids(self):
        with self.assertRaises(GraphServiceError):
            validate_relation_input(source_id="", target_source_id="b", relation_type="cite")


class RelationConversionTests(unittest.TestCase):
    def test_relation_to_dict(self):
        relation = SimpleNamespace(
            id="rel-1",
            source_id="src-1",
            target_source_id="src-2",
            relation_type="supersede",
            direction="directed",
            evidence="新版替代旧版",
            origin="system",
            status="confirmed",
            created_by="admin-1",
            confirmed_by="admin-2",
            created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            confirmed_at=None,
        )
        data = relation_to_dict(relation)
        self.assertEqual(data["relation_type"], "supersede")
        self.assertEqual(data["relation_label"], "替代")
        self.assertEqual(data["status"], "confirmed")
        self.assertIsNone(data["confirmed_at"])

    def test_system_supersede_edge(self):
        source = SimpleNamespace(id="new-id", replaced_source_id="old-id")
        edge = _system_supersede_edge(source)
        self.assertIsNotNone(edge)
        self.assertEqual(edge["source_id"], "old-id")
        self.assertEqual(edge["target_source_id"], "new-id")
        self.assertEqual(edge["relation_type"], "supersede")
        self.assertEqual(edge["origin"], "system")
        self.assertEqual(edge["status"], "confirmed")

    def test_system_supersede_edge_without_replaced(self):
        source = SimpleNamespace(id="new-id", replaced_source_id=None)
        self.assertIsNone(_system_supersede_edge(source))

    def test_graph_extraction_job_to_dict_includes_result_and_source_title(self):
        job = SimpleNamespace(
            id="job-1",
            source_id="source-1",
            status="succeeded",
            request_snapshot={
                "trigger": "publish",
                "result": {"created": 2, "skipped": 1, "unmatched_count": 3},
            },
            error_message="",
            created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            started_at=None,
            finished_at=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )

        data = graph_extraction_job_to_dict(job, source_title="员工请假制度")

        self.assertEqual(data["source_title"], "员工请假制度")
        self.assertEqual(data["trigger"], "publish")
        self.assertEqual(data["result"], {"created": 2, "skipped": 1, "unmatched_count": 3})


class GraphExtractionJobListTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_graph_extraction_jobs_joins_source_titles(self):
        job = SimpleNamespace(
            id="job-1",
            source_id="source-1",
            status="failed",
            request_snapshot={"trigger": "batch_backfill"},
            error_message="模型不可用",
            created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            started_at=None,
            finished_at=None,
        )
        db = AsyncMock()
        db.execute.return_value = SimpleNamespace(all=lambda: [(job, "员工请假制度")])

        jobs = await list_graph_relation_extraction_jobs(db, limit=8)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source_title"], "员工请假制度")
        self.assertEqual(jobs[0]["status"], "failed")
        self.assertEqual(jobs[0]["error_message"], "模型不可用")
        db.execute.assert_awaited_once()


class ConfirmedRelationsTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_source_ids_returns_empty(self):
        db = AsyncMock()
        result = await get_confirmed_relations(db, [])
        self.assertEqual(result, [])
        db.execute.assert_not_called()

    async def test_invalid_source_ids_filtered_out(self):
        db = AsyncMock()
        db.execute.return_value = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [])
        )
        result = await get_confirmed_relations(db, ["not-a-uuid", "also-bad"])
        self.assertEqual(result, [])

    async def test_returns_relations_for_valid_ids(self):
        db = AsyncMock()
        db.execute.return_value = SimpleNamespace(
            scalars=lambda: SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        id="rel-1",
                        source_id="11111111-1111-1111-1111-111111111111",
                        target_source_id="22222222-2222-2222-2222-222222222222",
                        relation_type="related",
                        direction="undirected",
                        evidence="",
                        origin="manual",
                        status="confirmed",
                        created_by="admin-1",
                        confirmed_by="admin-1",
                        created_at=None,
                        confirmed_at=None,
                    )
                ]
            )
        )
        result = await get_confirmed_relations(
            db, ["11111111-1111-1111-1111-111111111111"]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["relation_type"], "related")


class GraphExtractionTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_relations_filters_invalid_items(self):
        from app.plugins.company_knowledge.graph_extractor import _parse_relations

        raw = """
        ```json
        [
          {"relation_type": "cite", "target_title": "《员工考勤制度》", "evidence": "按考勤制度执行"},
          {"relation_type": "friendship", "target_title": "某文档"},
          {"relation_type": "related", "target_title": ""},
          "not-a-dict"
        ]
        ```
        """
        items = _parse_relations(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["relation_type"], "cite")

    def test_match_title_exact_and_containment(self):
        from app.plugins.company_knowledge.graph_extractor import _match_title

        known = [
            {"id": "a", "title": "员工考勤与休假管理制度"},
            {"id": "b", "title": "差旅报销管理办法"},
        ]
        self.assertEqual(_match_title("员工考勤与休假管理制度", known)["id"], "a")
        self.assertEqual(_match_title("《员工考勤与休假管理制度》", known)["id"], "a")
        self.assertEqual(_match_title("员工考勤与休假管理制度（V2）", known), None)

    def test_match_title_ignores_too_short(self):
        from app.plugins.company_knowledge.graph_extractor import _match_title

        known = [{"id": "a", "title": "考勤"}]
        self.assertIsNone(_match_title("考勤", known))

    async def test_extract_relations_from_text_matches_and_unmatched(self):
        from app.plugins.company_knowledge.graph_extractor import extract_relations_from_text

        known = [
            {"id": "src-a", "title": "员工考勤与休假管理制度"},
            {"id": "src-b", "title": "差旅报销管理办法"},
        ]

        async def fake_chat(prompt, system=""):
            return (
                '[{"relation_type": "cite", "target_title": "员工考勤与休假管理制度", "evidence": "按考勤制度执行"}, '
                '{"relation_type": "related", "target_title": "不存在的制度", "evidence": "关联"}]'
            )

        with patch(
            "app.plugins.company_knowledge.graph_extractor.gateway.chat",
            side_effect=fake_chat,
        ):
            matched, unmatched = await extract_relations_from_text(
                "正文内容", source_title="假期管理办法", known_titles=known
            )

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["target_source_id"], "src-a")
        self.assertEqual(matched[0]["relation_type"], "cite")
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["target_title"], "不存在的制度")


class GraphExtractionJobTests(unittest.IsolatedAsyncioTestCase):
    SOURCE_ID = "11111111-1111-1111-1111-111111111111"
    JOB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    def _source(self):
        return SimpleNamespace(id=self.SOURCE_ID, status="published", published_at=None)

    async def test_enqueue_creates_queued_job_for_published_source(self):
        source = self._source()
        db = SimpleNamespace(
            get=AsyncMock(return_value=source),
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        job, created = await enqueue_graph_relation_extraction(
            db,
            source_id=self.SOURCE_ID,
            admin_id="admin-1",
            trigger="publish",
        )

        self.assertTrue(created)
        self.assertEqual(job.job_type, "graph_extract")
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.request_snapshot, {"trigger": "publish"})
        db.add.assert_called_once_with(job)
        db.commit.assert_awaited_once()

    async def test_enqueue_reuses_active_job_for_same_source(self):
        source = self._source()
        active_job = SimpleNamespace(id=self.JOB_ID, status="running")
        db = SimpleNamespace(
            get=AsyncMock(return_value=source),
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: active_job)),
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        job, created = await enqueue_graph_relation_extraction(
            db,
            source_id=self.SOURCE_ID,
            admin_id="admin-1",
            trigger="manual",
        )

        self.assertIs(job, active_job)
        self.assertFalse(created)
        db.add.assert_not_called()
        db.commit.assert_not_awaited()

    async def test_batch_enqueue_skips_active_and_currently_scanned_sources(self):
        now = datetime(2026, 8, 10, tzinfo=timezone.utc)
        source_a = SimpleNamespace(id="source-a", published_at=now)
        source_b = SimpleNamespace(id="source-b", published_at=now)
        source_c = SimpleNamespace(id="source-c", published_at=now)
        sources_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [source_a, source_b, source_c]))
        active_result = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(source_id="source-b", status="running")])
        )
        completed_result = SimpleNamespace(all=lambda: [("source-a", now)])
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[sources_result, active_result, completed_result]),
            add_all=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

        jobs, skipped = await enqueue_graph_relation_extractions_for_published_sources(
            db,
            admin_id="admin-1",
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_id, "source-c")
        self.assertEqual(jobs[0].request_snapshot, {"trigger": "batch_backfill"})
        self.assertEqual(skipped, 2)
        db.add_all.assert_called_once_with(jobs)

    async def test_executor_records_result_without_auto_confirming_relations(self):
        job = SimpleNamespace(
            id=self.JOB_ID,
            source_id=self.SOURCE_ID,
            job_type="graph_extract",
            status="queued",
            requested_by="admin-1",
            request_snapshot={"trigger": "publish"},
            error_message="",
            succeeded_chunks=0,
            failed_chunks=0,
            started_at=None,
            finished_at=None,
        )
        source = self._source()
        db = SimpleNamespace(
            get=AsyncMock(side_effect=[job, source]),
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: self.JOB_ID)),
            commit=AsyncMock(),
            refresh=AsyncMock(),
            rollback=AsyncMock(),
        )
        with patch(
            "app.plugins.company_knowledge.graph_service.extract_source_relations",
            AsyncMock(return_value={"created": 2, "skipped": 1, "unmatched": [{"target_title": "未收录制度"}]}),
        ) as extract:
            result = await execute_graph_relation_extraction_job(db, job_id=self.JOB_ID)

        self.assertIs(result, job)
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.succeeded_chunks, 1)
        self.assertEqual(job.request_snapshot["result"], {"created": 2, "skipped": 1, "unmatched_count": 1})
        extract.assert_awaited_once_with(db, source_id=self.SOURCE_ID, admin_id="admin-1")

    async def test_executor_cancels_job_when_source_is_no_longer_published(self):
        job = SimpleNamespace(
            id=self.JOB_ID,
            source_id=self.SOURCE_ID,
            job_type="graph_extract",
            status="queued",
            error_message="",
            finished_at=None,
        )
        source = SimpleNamespace(id=self.SOURCE_ID, status="archived")
        db = SimpleNamespace(get=AsyncMock(side_effect=[job, source]), commit=AsyncMock())

        result = await execute_graph_relation_extraction_job(db, job_id=self.JOB_ID)

        self.assertIs(result, job)
        self.assertEqual(job.status, "cancelled")
        self.assertIn("下架", job.error_message)


class GraphExtractionPublishEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_queues_background_graph_extraction(self):
        from fastapi import BackgroundTasks
        from app.api import admin_company_knowledge as api

        source = SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
        job = SimpleNamespace(id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        background_tasks = BackgroundTasks()
        db = AsyncMock()
        with (
            patch.object(api, "publish_company_source", AsyncMock(return_value=source)),
            patch.object(api, "enqueue_graph_relation_extraction", AsyncMock(return_value=(job, True))) as enqueue,
            patch.object(api, "source_to_dict", return_value={"id": str(source.id)}),
            patch.object(api, "job_to_dict", return_value={"id": str(job.id), "status": "queued"}),
        ):
            response = await api.publish_source(
                str(source.id),
                background_tasks,
                admin=SimpleNamespace(id="admin-1"),
                db=db,
            )

        self.assertTrue(response["success"])
        self.assertIn("后台生成关系草稿", response["message"])
        enqueue.assert_awaited_once_with(
            db,
            source_id=response["data"]["source"]["id"],
            admin_id="admin-1",
            trigger="publish",
        )
        self.assertEqual(len(background_tasks.tasks), 1)


class RelatedSourcesTests(unittest.IsolatedAsyncioTestCase):
    SRC_A = "11111111-1111-1111-1111-111111111111"
    SRC_B = "22222222-2222-2222-2222-222222222222"

    def _chunk(self, source_id, chunk_id="c1"):
        from app.plugins.company_knowledge.retriever import RetrievedChunk

        return RetrievedChunk(
            chunk_id=chunk_id,
            source_id=source_id,
            title="命中制度",
            version="1.0",
            effective_at="2026-08-10",
            section_path="第一章",
            content="正文",
            similarity=0.6,
        )

    async def test_disabled_type_returns_empty(self):
        from app.api.company_knowledge import _build_related_sources

        db = AsyncMock()
        result = await _build_related_sources(db, [self._chunk(self.SRC_A)], "faq")
        self.assertEqual(result, [])
        db.execute.assert_not_called()

    async def test_returns_neighbor_with_title(self):
        from app.api.company_knowledge import _build_related_sources
        from app.api import company_knowledge as module

        relations = [
            {
                "source_id": self.SRC_A,
                "target_source_id": self.SRC_B,
                "relation_type": "cite",
                "relation_label": "引用",
                "direction": "directed",
            }
        ]
        db = AsyncMock()
        db.execute.return_value = SimpleNamespace(
            all=lambda: [(self.SRC_B, "请假管理制度")]
        )
        with patch.object(module, "get_confirmed_relations", AsyncMock(return_value=relations)):
            result = await _build_related_sources(db, [self._chunk(self.SRC_A)], "policy")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "请假管理制度")
        self.assertEqual(result[0]["relation_type"], "cite")
        self.assertEqual(result[0]["source_id"], self.SRC_B)

    async def test_hit_both_ends_does_not_include_neighbor(self):
        from app.api.company_knowledge import _build_related_sources
        from app.api import company_knowledge as module

        relations = [
            {
                "source_id": self.SRC_A,
                "target_source_id": self.SRC_B,
                "relation_type": "related",
                "relation_label": "关联",
                "direction": "undirected",
            }
        ]
        db = AsyncMock()
        with patch.object(module, "get_confirmed_relations", AsyncMock(return_value=relations)):
            result = await _build_related_sources(
                db, [self._chunk(self.SRC_A), self._chunk(self.SRC_B, chunk_id="c2")], "policy"
            )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
