"""公司制度资料的纯本地处理测试，不依赖数据库、Embedding 或聊天模型。"""

import unittest
from pathlib import Path

from app.plugins.company_knowledge.chunker import chunk_text
from app.plugins.company_knowledge.importer import SourceImportError, read_text_source, to_markdown
from app.plugins.company_knowledge.prompts import COMPANY_KNOWLEDGE_SYSTEM_PROMPT, build_answer_prompt


class CompanyKnowledgePipelineTests(unittest.TestCase):
    fixture_dir = Path(__file__).parent / "fixtures" / "company_knowledge"

    def test_utf8_markdown_fixture_is_indexable_and_hashed(self):
        file_path = self.fixture_dir / "attendance-leave-v2.md"
        imported = read_text_source(file_path.name, file_path.read_bytes())

        self.assertEqual(imported.source_format, "md")
        self.assertIn("年假应至少提前五个工作日", imported.content)
        self.assertEqual(len(imported.content_hash), 64)

    def test_txt_fixture_is_indexable(self):
        file_path = self.fixture_dir / "office-conduct-v1.txt"
        imported = read_text_source(file_path.name, file_path.read_bytes())

        self.assertEqual(imported.source_format, "txt")
        self.assertIn("离开工位", imported.content)

    def test_txt_is_converted_to_reviewable_markdown(self):
        file_path = self.fixture_dir / "office-conduct-v1.txt"
        imported = read_text_source(file_path.name, file_path.read_bytes())

        markdown, warnings = to_markdown(imported, "办公行为规范（测试资料）")

        self.assertTrue(markdown.startswith("# 办公行为规范（测试资料）"))
        self.assertIn("离开工位", markdown)
        self.assertTrue(warnings)

    def test_import_rejects_non_text_format_and_non_utf8_content(self):
        with self.assertRaisesRegex(SourceImportError, "TXT 或 Markdown"):
            read_text_source("制度.pdf", b"not-a-pdf")
        with self.assertRaisesRegex(SourceImportError, "UTF-8"):
            read_text_source("制度.txt", b"\xff\xfe\x00")

    def test_markdown_chunks_keep_heading_path_and_overlap(self):
        body = "第一条年假申请应提前提交。" * 60
        chunks = chunk_text(
            f"# 人事制度\n\n## 年假\n{body}\n\n## 事假\n事假按实际情况审批。",
            source_format="md",
            max_chars=180,
            overlap_chars=30,
        )

        self.assertGreater(len(chunks), 2)
        self.assertEqual(chunks[0].section_path, "人事制度 / 年假")
        self.assertTrue(all(chunk.chunk_index == index for index, chunk in enumerate(chunks)))
        self.assertTrue(any(chunk.section_path == "人事制度 / 事假" for chunk in chunks))
        self.assertIn(chunks[0].content[-20:], chunks[1].content)

    def test_prompt_only_contains_explicit_retrieval_evidence(self):
        prompt = build_answer_prompt(
            "年假如何申请？",
            [
                {
                    "title": "员工休假制度",
                    "version": "V1.2",
                    "effective_at": "2026-01-01",
                    "section_path": "休假 / 年假",
                    "content": "员工应提前三个工作日提交年假申请。",
                }
            ],
        )

        self.assertIn("员工应提前三个工作日提交年假申请。", prompt)
        self.assertIn("版本 V1.2", prompt)
        self.assertIn("只能依据本次提供的公司资料片段", COMPANY_KNOWLEDGE_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
