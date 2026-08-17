import unittest

from routers.convert import _text_filename_base


class TextFilenameTests(unittest.TestCase):
    def test_uses_first_meaningful_text(self):
        self.assertEqual(_text_filename_base("\n# 整式综合单元测试卷\n正文"), "整式综合单元测试卷")

    def test_removes_unsafe_filename_characters(self):
        self.assertEqual(_text_filename_base('  测试/文档:*?"<>|  '), "测试文档")


if __name__ == "__main__":
    unittest.main()
