"""Convert pasted Markdown/LaTeX text to a formula-safe PDF."""

import os

from converters.text_to_word import convert as text_to_word
from utils import libreoffice_convert


def convert(text: str, output_path: str, progress_cb=None):
    work_dir = os.path.dirname(output_path)
    intermediate = os.path.join(work_dir, ".pasted_text_source.docx")
    if progress_cb:
        progress_cb(10, "正在渲染 PDF 数学公式...")

    def word_progress(pct: int, stage: str = ""):
        if progress_cb:
            progress_cb(10 + round(pct * 0.65), stage)

    # LibreOffice drops Word's native OMML equations when importing DOCX on
    # some Linux builds.  Use high-resolution transparent equation images only
    # in this temporary document; regular Word downloads still use editable
    # native equations.
    text_to_word(text, intermediate, word_progress, math_mode="image")
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
