"""BM25 关键词召回与 RRF 融合的纯本地测试，不依赖数据库或聊天模型。"""

import unittest

from app.plugins.company_knowledge.keyword_retriever import BM25Index, rrf_merge


class BM25IndexTests(unittest.TestCase):
    def _docs(self):
        return [
            ("chunk-1", "员工年假应至少提前五个工作日申请，逾期不予受理。"),
            ("chunk-2", "费用报销需要提交发票和审批单，财务部门审核。"),
            ("chunk-3", "出差申请应提前一天提交，差旅标准按级别执行。"),
        ]

    def test_returns_relevant_chunk_first(self):
        index = BM25Index(self._docs())
        hits = index.search("年假如何申请")
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk_id, "chunk-1")

    def test_returns_empty_for_unknown_terms(self):
        index = BM25Index(self._docs())
        hits = index.search("量子计算与火星殖民")
        self.assertEqual(hits, [])

    def test_scores_are_descending(self):
        index = BM25Index(self._docs())
        hits = index.search("报销发票审核")
        self.assertTrue(hits)
        scores = [hit.score for hit in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_index_returns_empty(self):
        index = BM25Index([])
        self.assertEqual(index.search("任意查询"), [])

    def test_top_k_limits_results(self):
        index = BM25Index(self._docs())
        hits = index.search("申请 提交 审核 发票 年假 报销 出差", top_k=2)
        self.assertLessEqual(len(hits), 2)


class RRFMergeTests(unittest.TestCase):
    def test_merges_rankings_by_reciprocal_rank(self):
        vector = ["a", "b", "c", "d"]
        keyword = ["b", "c", "a", "e"]
        merged = rrf_merge(vector, keyword, limit=4)
        self.assertEqual(merged[0], "b")  # 两路都靠前
        self.assertIn("a", merged)
        self.assertIn("c", merged)

    def test_single_side_ranked(self):
        vector = ["x", "y", "z"]
        keyword = []
        merged = rrf_merge(vector, keyword, limit=2)
        self.assertEqual(merged, ["x", "y"])

    def test_limit_respected(self):
        vector = ["a", "b", "c", "d", "e", "f", "g"]
        keyword = []
        merged = rrf_merge(vector, keyword, limit=3)
        self.assertEqual(len(merged), 3)

    def test_deduplicates_overlapping_ids(self):
        vector = ["a", "b"]
        keyword = ["a", "b"]
        merged = rrf_merge(vector, keyword, limit=10)
        self.assertEqual(merged.count("a"), 1)
        self.assertEqual(merged.count("b"), 1)


if __name__ == "__main__":
    unittest.main()
