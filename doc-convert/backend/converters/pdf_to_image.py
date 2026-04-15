import os
import zipfile
import fitz


def _render(input_path: str, output_path: str, fmt: str, dpi: int = 150, progress_cb=None):
    doc = fitz.open(input_path)
    total = len(doc)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)

    if total == 1:
        pix = doc[0].get_pixmap(matrix=matrix)
        pix.save(output_path)
        if progress_cb:
            progress_cb(100)
        return

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes(fmt)
            zf.writestr(f"page_{i+1:03d}.{fmt}", img_bytes)
            if progress_cb:
                progress_cb(int((i + 1) / total * 100), f"第 {i+1}/{total} 页")


def convert_png(input_path: str, output_path: str, progress_cb=None):
    # 多页时输出 zip，单页直接输出 png
    doc = fitz.open(input_path)
    if len(doc) == 1:
        _out = output_path.replace(".zip", ".png")
    else:
        _out = output_path if output_path.endswith(".zip") else output_path + ".zip"
    _render(input_path, _out, "png", progress_cb=progress_cb)


def convert_jpg(input_path: str, output_path: str, progress_cb=None):
    doc = fitz.open(input_path)
    if len(doc) == 1:
        _out = output_path.replace(".zip", ".jpg")
    else:
        _out = output_path if output_path.endswith(".zip") else output_path + ".zip"
    _render(input_path, _out, "jpeg", progress_cb=progress_cb)
