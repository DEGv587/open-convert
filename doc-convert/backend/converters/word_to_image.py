import os
import tempfile
from converters.word_to_pdf import convert as to_pdf
from converters.pdf_to_image import convert_png as pdf_to_png, convert_jpg as pdf_to_jpg


def _via_pdf(input_path: str, output_path: str, fmt: str, progress_cb=None):
    work_dir = os.path.dirname(output_path)
    pdf_path = os.path.join(work_dir, "_tmp_word.pdf")

    def cb1(pct, stage=""):
        if progress_cb:
            progress_cb(int(pct * 0.4), stage)

    to_pdf(input_path, pdf_path, cb1)

    def cb2(pct, stage=""):
        if progress_cb:
            progress_cb(40 + int(pct * 0.6), stage)

    if fmt == "png":
        pdf_to_png(pdf_path, output_path, cb2)
    else:
        pdf_to_jpg(pdf_path, output_path, cb2)

    if os.path.exists(pdf_path):
        os.remove(pdf_path)


def convert_png(input_path: str, output_path: str, progress_cb=None):
    _via_pdf(input_path, output_path, "png", progress_cb)


def convert_jpg(input_path: str, output_path: str, progress_cb=None):
    _via_pdf(input_path, output_path, "jpg", progress_cb)
