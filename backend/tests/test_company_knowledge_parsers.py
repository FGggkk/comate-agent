"""PDF / Word 文档解析适配器与导入链路的纯本地测试。"""

import unittest
from pathlib import Path

from app.plugins.company_knowledge.importer import (
    MAX_SOURCE_BYTES,
    SourceImportError,
    read_text_source,
    to_markdown,
)
from app.plugins.company_knowledge.parsers import DocumentParseError, parse_document


class CompanyKnowledgeParserTests(unittest.TestCase):
    fixture_dir = Path(__file__).parent / "fixtures" / "company_knowledge"

    def test_pdf_fixture_is_parsed_to_text(self):
        file_path = self.fixture_dir / "attendance-leave-v1.pdf"
        imported = read_text_source(file_path.name, file_path.read_bytes())
        self.assertEqual(imported.source_format, "pdf")
        self.assertIn("年假申请", imported.content)
        self.assertIn("五个工作日", imported.content)
        self.assertEqual(len(imported.content_hash), 64)

    def test_docx_fixture_is_parsed_with_table(self):
        file_path = self.fixture_dir / "expense-reimburse-v1.docx"
        imported = read_text_source(file_path.name, file_path.read_bytes())
        self.assertEqual(imported.source_format, "docx")
        self.assertIn("报销申请", imported.content)
        self.assertIn("|", imported.content)  # 表格转 Markdown 表格

    def test_pdf_to_markdown_adds_title_and_warnings(self):
        file_path = self.fixture_dir / "attendance-leave-v1.pdf"
        imported = read_text_source(file_path.name, file_path.read_bytes())
        markdown, warnings = to_markdown(imported, "员工年假管理制度")
        self.assertTrue(markdown.startswith("# 员工年假管理制度"))
        self.assertTrue(warnings)

    def test_invalid_pdf_rejected(self):
        with self.assertRaises(SourceImportError):
            read_text_source("bad.pdf", b"this is not a pdf")

    def test_invalid_docx_rejected(self):
        with self.assertRaises(SourceImportError):
            read_text_source("bad.docx", b"not a docx at all")

    def test_unsupported_extension_rejected(self):
        with self.assertRaisesRegex(SourceImportError, "支持的格式"):
            read_text_source("report.xlsx", b"whatever")

    def test_oversize_rejected(self):
        big = b"x" * (MAX_SOURCE_BYTES + 1)
        with self.assertRaisesRegex(SourceImportError, "10MB"):
            read_text_source("big.pdf", big)

    def test_parse_document_rejects_unknown_suffix(self):
        with self.assertRaises(DocumentParseError):
            parse_document("file.unknown", b"data")


if __name__ == "__main__":
    unittest.main()
