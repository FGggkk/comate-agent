"""A1 Embedding 突变检测切分测试：不依赖数据库与真实 Embedding 服务。"""

import unittest
from unittest.mock import patch

from app.plugins.company_knowledge.chunker import (
    _cosine_similarity,
    chunk_text,
    chunk_text_semantic,
)

# 构造的 4 维向量：p0/p1 相近、p1/p2 相远、p2/p3 相近
EMB_NEAR_A = [1.0, 0.0, 0.0, 0.0]
EMB_NEAR_B = [0.9, 0.1, 0.0, 0.0]
EMB_FAR = [0.0, 0.0, 1.0, 0.0]
EMB_NEAR_C = [0.0, 0.0, 0.9, 0.1]

P0 = "考勤记录以打卡机数据为准，员工应在上下班时打卡。"
P1 = "漏打卡的员工可以在一周内提交补卡申请，说明原因。"
P2 = "公司年会将于十二月举行，请各部门提前报送节目。"
P3 = "年会奖品由行政部统一采购，预算已获批。"
P4 = "办公用品申领需填写领用单，经部门负责人签字。"
P5 = "文具类用品由前台统一保管，领用时登记数量。"


async def _fake_embeddings(texts):
    mapping = {
        P0: EMB_NEAR_A,
        P1: EMB_NEAR_B,
        P2: EMB_FAR,
        P3: EMB_NEAR_C,
    }
    return [mapping.get(t, EMB_NEAR_A) for t in texts]


class SemanticChunkingTests(unittest.IsolatedAsyncioTestCase):
    async def test_semantic_break_separates_unrelated_paragraphs(self):
        body = "\n\n".join([P0, P1, P2, P3])
        with patch(
            "app.plugins.company_knowledge.chunker.get_embeddings_batch",
            side_effect=_fake_embeddings,
        ):
            chunks = await chunk_text_semantic(body, source_format="txt", max_chars=1000, min_similarity=0.75)

        self.assertEqual(len(chunks), 2, [c.content for c in chunks])
        self.assertEqual(chunks[0].content, "\n\n".join([P0, P1]))
        self.assertEqual(chunks[1].content, "\n\n".join([P2, P3]))

    async def test_similar_paragraphs_stay_together(self):
        # 全部段落相近（P5 不在 mapping，回退为 EMB_NEAR_A，与 P0 相同）：只受 max_chars 约束
        body = "\n\n".join([P0, P1, P5])
        with patch(
            "app.plugins.company_knowledge.chunker.get_embeddings_batch",
            side_effect=_fake_embeddings,
        ):
            chunks = await chunk_text_semantic(body, source_format="txt", max_chars=1000, min_similarity=0.75)

        self.assertEqual(len(chunks), 1, [c.content for c in chunks])
        self.assertIn(P0, chunks[0].content)
        self.assertIn(P5, chunks[0].content)

    async def test_embedding_failure_falls_back_to_rule_chunking(self):
        body = "\n\n".join([P0, P1, P2, P3])
        with patch(
            "app.plugins.company_knowledge.chunker.get_embeddings_batch",
            return_value=None,
        ):
            semantic_chunks = await chunk_text_semantic(body, source_format="txt", max_chars=500, min_similarity=0.75)

        rule_chunks = chunk_text(body, source_format="txt", max_chars=500, overlap_chars=100)
        self.assertEqual(
            [c.content for c in semantic_chunks],
            [c.content for c in rule_chunks],
        )

    async def test_long_paragraph_split_by_sentences(self):
        # 超过 max_chars(120) 的长段落按句子边界切分，P0 与 P4 各自独立成块（被长段落隔开）
        long_paragraph = "".join(
            [
                "第一句说明考勤规则与打卡方式。",
                "第二句说明漏打卡补卡申请时限。",
                "第三句说明加班审批与调休安排。",
                "第四句说明请假须提前报备直属上级。",
                "第五句说明外勤需部门负责人审批。",
                "第六句说明考勤异常由人事复核处理。",
                "第七句说明月度考勤汇总发布安排。",
                "第八句说明异议申诉窗口与流程。",
                "第九句说明考勤数据保留期限。",
                "第十句说明本制度解释权归人事部。",
            ]
        )
        self.assertGreater(len(long_paragraph), 120)
        body = "\n\n".join([P0, long_paragraph, P4])
        with patch(
            "app.plugins.company_knowledge.chunker.get_embeddings_batch",
            side_effect=_fake_embeddings,
        ):
            chunks = await chunk_text_semantic(body, source_format="txt", max_chars=120, min_similarity=0.75)

        contents = [c.content for c in chunks]
        self.assertEqual(contents[0], P0)
        self.assertTrue(any("第一句" in c and "第二句" in c for c in contents), contents)
        self.assertEqual(contents[-1], P4)

    async def test_min_similarity_threshold_controls_break(self):
        # P2 与 P3 余弦约 0.994：min_similarity 提到 0.999 后不再断开
        body = "\n\n".join([P2, P3])
        with patch(
            "app.plugins.company_knowledge.chunker.get_embeddings_batch",
            side_effect=_fake_embeddings,
        ):
            strict_chunks = await chunk_text_semantic(body, source_format="txt", max_chars=1000, min_similarity=0.999)
        self.assertEqual(len(strict_chunks), 2, [c.content for c in strict_chunks])

    def test_cosine_similarity(self):
        self.assertAlmostEqual(_cosine_similarity([1, 0, 0], [1, 0, 0]), 1.0)
        self.assertAlmostEqual(_cosine_similarity([1, 0, 0], [0, 1, 0]), 0.0)
        self.assertEqual(_cosine_similarity([0, 0, 0], [1, 0, 0]), 0.0)
        self.assertAlmostEqual(_cosine_similarity([1, 1, 0], [1, 1, 0]), 1.0)


class LlmRefineChunkTests(unittest.IsolatedAsyncioTestCase):
    def _chunks(self):
        from app.plugins.company_knowledge.chunker import TextChunk

        return [
            TextChunk(chunk_index=0, section_path="考勤", content="第一段讲考勤打卡规则。", token_count=10),
            TextChunk(chunk_index=1, section_path="考勤", content="第二段讲漏打卡补卡申请。", token_count=10),
            TextChunk(chunk_index=2, section_path="请假", content="第三段讲年假申请流程。", token_count=10),
        ]

    async def test_merge_with_next(self):
        from app.plugins.company_knowledge.llm_chunker import llm_refine_chunks

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            return_value='[{"chunk_index": 0, "action": "merge_with_next", "split_at": null, "reason": "同属考勤"}, {"chunk_index": 1, "action": "keep", "reason": ""}, {"chunk_index": 2, "action": "keep", "reason": ""}]',
        ):
            refined, warnings = await llm_refine_chunks(self._chunks(), source_title="考勤制度", target_len=500)

        self.assertEqual(warnings, [])
        self.assertEqual(len(refined), 2)
        self.assertIn("第一段讲考勤打卡规则。", refined[0].content)
        self.assertIn("第二段讲漏打卡补卡申请。", refined[0].content)
        self.assertEqual(refined[1].content, "第三段讲年假申请流程。")

    async def test_chained_merge(self):
        from app.plugins.company_knowledge.llm_chunker import llm_refine_chunks

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            return_value='[{"chunk_index": 0, "action": "merge_with_next"}, {"chunk_index": 1, "action": "merge_with_next"}, {"chunk_index": 2, "action": "keep"}]',
        ):
            refined, _ = await llm_refine_chunks(self._chunks(), source_title="考勤制度", target_len=500)

        self.assertEqual(len(refined), 1)
        self.assertIn("第三段讲年假申请流程。", refined[0].content)

    async def test_merge_overflow_is_ignored(self):
        from app.plugins.company_knowledge.llm_chunker import llm_refine_chunks

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            return_value='[{"chunk_index": 0, "action": "merge_with_next"}, {"chunk_index": 1, "action": "keep"}, {"chunk_index": 2, "action": "keep"}]',
        ):
            refined, warnings = await llm_refine_chunks(self._chunks(), source_title="考勤制度", target_len=10)

        self.assertEqual(len(refined), 3)
        self.assertTrue(any("超长" in w for w in warnings))

    async def test_split_at_sentence_boundary(self):
        from app.plugins.company_knowledge.chunker import TextChunk
        from app.plugins.company_knowledge.llm_chunker import llm_refine_chunks

        chunks = [
            TextChunk(chunk_index=0, section_path="", content="第一句讲考勤。第二句讲请假。第三句讲薪资。", token_count=12),
        ]
        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            return_value='[{"chunk_index": 0, "action": "split", "split_at": 7, "reason": "主题不同"}]',
        ):
            refined, _ = await llm_refine_chunks(chunks, source_title="综合制度", target_len=500)

        self.assertEqual(len(refined), 2)
        self.assertEqual(refined[0].content, "第一句讲考勤。")
        self.assertEqual(refined[1].content, "第二句讲请假。第三句讲薪资。")

    async def test_llm_failure_falls_back_with_warning(self):
        from app.plugins.company_knowledge.llm_chunker import llm_refine_chunks

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            side_effect=RuntimeError("模型超时"),
        ):
            refined, warnings = await llm_refine_chunks(self._chunks(), source_title="考勤制度", target_len=500)

        self.assertEqual(len(refined), 3)
        self.assertTrue(any("不可用" in w for w in warnings))

    async def test_invalid_json_falls_back_with_warning(self):
        from app.plugins.company_knowledge.llm_chunker import llm_refine_chunks

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            return_value="抱歉我无法回答",
        ):
            refined, warnings = await llm_refine_chunks(self._chunks(), source_title="考勤制度", target_len=500)

        self.assertEqual(len(refined), 3)
        self.assertTrue(any("不可用" in w or "未返回有效决策" in w for w in warnings))


class ContextualDescriptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_contextual_descriptions(self):
        from app.plugins.company_knowledge.chunker import TextChunk
        from app.plugins.company_knowledge.llm_chunker import generate_contextual_descriptions

        chunks = [
            TextChunk(chunk_index=0, section_path="考勤", content="第一段讲考勤打卡规则。", token_count=10),
            TextChunk(chunk_index=1, section_path="考勤", content="第二段讲漏打卡补卡申请。", token_count=10),
        ]

        async def fake_chat(prompt, system=""):
            return "这是《考勤制度》考勤章节关于打卡的说明。"

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            side_effect=fake_chat,
        ):
            descriptions = await generate_contextual_descriptions(chunks, source_title="考勤制度")

        self.assertEqual(len(descriptions), 2)
        self.assertTrue(all("考勤" in d for d in descriptions))

    async def test_single_failure_returns_empty_without_aborting(self):
        from app.plugins.company_knowledge.chunker import TextChunk
        from app.plugins.company_knowledge.llm_chunker import generate_contextual_descriptions

        chunks = [
            TextChunk(chunk_index=0, section_path="考勤", content="第一段。", token_count=4),
            TextChunk(chunk_index=1, section_path="考勤", content="第二段。", token_count=4),
        ]

        async def flaky_chat(prompt, system=""):
            if "本分片内容：\n第一段" in prompt:
                raise RuntimeError("模型超时")
            return "这是关于考勤第二段的说明。"

        with patch(
            "app.plugins.company_knowledge.llm_chunker.gateway.chat",
            side_effect=flaky_chat,
        ):
            descriptions = await generate_contextual_descriptions(chunks, source_title="考勤制度")

        self.assertEqual(len(descriptions), 2)
        self.assertEqual(descriptions[0], "")
        self.assertIn("考勤第二段", descriptions[1])

    def test_answer_prompt_includes_contextual_description(self):
        from app.plugins.company_knowledge.prompts import build_answer_prompt

        prompt = build_answer_prompt(
            "年假怎么申请？",
            [
                {
                    "title": "考勤制度",
                    "version": "V1.0",
                    "effective_at": "2026-01-01",
                    "section_path": "第四章 年假",
                    "content": "年假申请需提前五个工作日。",
                    "contextual_description": "这是《考勤制度》第四章年假部分的申请条款。",
                }
            ],
        )
        self.assertIn("上下文：这是《考勤制度》第四章年假部分的申请条款。", prompt)
        self.assertIn("年假申请需提前五个工作日。", prompt)

    def test_answer_prompt_without_context_stays_compact(self):
        from app.plugins.company_knowledge.prompts import build_answer_prompt

        prompt = build_answer_prompt(
            "年假怎么申请？",
            [
                {
                    "title": "考勤制度",
                    "version": "V1.0",
                    "effective_at": "2026-01-01",
                    "section_path": "第四章 年假",
                    "content": "年假申请需提前五个工作日。",
                }
            ],
        )
        self.assertNotIn("上下文：", prompt)


if __name__ == "__main__":
    unittest.main()
