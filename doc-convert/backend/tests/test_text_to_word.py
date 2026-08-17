import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from converters.text_to_word import convert


class TextToWordTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_latex_is_written_as_native_omml(self):
        source = (
            "# 公式测试\n\n"
            "1. 计算 $x^2 + \\dfrac{1}{2} + \\sqrt{y}$\n\n"
            "$$\\begin{align*}\n"
            "y^2&=x^2+1\\\\\n"
            "z&=\\sqrt{y}\n"
            "\\end{align*}$$"
        )
        output = self.work_dir / "formula.docx"

        convert(source, str(output))

        document = Document(output)
        self.assertIn("公式测试", "\n".join(paragraph.text for paragraph in document.paragraphs))
        with zipfile.ZipFile(output) as package:
            xml = package.read("word/document.xml").decode("utf-8")
        self.assertGreaterEqual(xml.count("<m:oMath"), 2)
        self.assertIn("<m:f>", xml)
        self.assertIn("<m:rad>", xml)
        self.assertIn("<m:oMathPara", xml)
        self.assertNotIn("dfrac", xml)
        self.assertNotIn("begin{align", xml)

    def test_empty_text_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "粘贴的文本不能为空"):
            convert("  ", str(self.work_dir / "empty.docx"))

    def test_blank_lines_use_plain_underscore_text_outside_math(self):
        output = self.work_dir / "blank-lines.docx"
        convert(
            "9. 单项式的系数是＿＿＿＿，次数是＿＿＿＿。\n"
            "10. y^4\\cdot y^5=________\n"
            "11. (-2)^0=_ _ _ _ _ _ _ _",
            str(output),
        )

        document = Document(output)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertNotIn("＿", text)
        self.assertIn("____", text)
        with zipfile.ZipFile(output) as package:
            xml = package.read("word/document.xml").decode("utf-8")
        self.assertNotIn('<w:u w:val="single"/>', xml)
        self.assertGreaterEqual(xml.count("________"), 1)
        self.assertNotIn("<m:sSub>", xml)

    def test_plain_text_with_unwrapped_latex_keeps_formula_structure(self):
        source = (
            "整式综合单元测试卷\n\n"
            "一、选择题（每题3分，共24分）\n"
            "1. 下列属于单项式的是（　　）\n"
            "A.x-y　B.\\dfrac{2}{5}x　C.x^2+3x　D.\\dfrac{1}{a}\n"
            "\\begin{align*}\n"
            "y^2&=x^2+1\\\\\n"
            "z&=\\sqrt{y}\n"
            "\\end{align*}"
        )
        output = self.work_dir / "plain-text-formula.docx"

        convert(source, str(output))

        document = Document(output)
        self.assertEqual(document.paragraphs[0].text, "整式综合单元测试卷")
        self.assertEqual(document.paragraphs[0].alignment, 1)
        with zipfile.ZipFile(output) as package:
            xml = package.read("word/document.xml").decode("utf-8")
        self.assertGreaterEqual(xml.count("<m:oMath"), 4)
        self.assertGreaterEqual(xml.count("<m:f>"), 2)
        self.assertIn("<m:sSup>", xml)
        self.assertIn("<m:rad>", xml)
        self.assertIn("<m:oMathPara", xml)
        self.assertNotIn("dfrac", xml)
        self.assertNotIn("begin{align", xml)


if __name__ == "__main__":
    unittest.main()
