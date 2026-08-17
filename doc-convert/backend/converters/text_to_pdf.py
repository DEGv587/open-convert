"""Convert pasted Markdown/LaTeX text to PDF through the DOCX renderer."""

import os

from converters.text_to_word import convert as text_to_word
from utils import libreoffice_convert


def convert(text: str, output_path: str, progress_cb=None):
    work_dir = os.path.dirname(output_path)
    intermediate = os.path.join(work_dir, ".pasted_text_source.docx")
    if progress_cb:
        progress_cb(10, "正在生成含原生公式的 Word...")

    def word_progress(pct: int, stage: str = ""):
        if progress_cb:
            progress_cb(10 + round(pct * 0.65), stage)

    text_to_word(text, intermediate, word_progress)
    if progress_cb:
        progress_cb(85, "正在输出 PDF...")
    generated = libreoffice_convert(intermediate, work_dir, "pdf")
    if generated != output_path:
        os.replace(generated, output_path)
    try:
        os.remove(intermediate)
    except OSError:
        pass
    if progress_cb:
        progress_cb(100, "PDF 文档已生成")
