import img2pdf


def convert(input_paths: list, output_path: str, progress_cb=None):
    """多图合并为 PDF，input_paths 已按前端指定顺序排列。"""
    if progress_cb:
        progress_cb(10, "合并图片...")
    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(input_paths))
    if progress_cb:
        progress_cb(100)


def convert_single(input_path: str, output_path: str, progress_cb=None):
    """单张图片转 PDF。"""
    convert([input_path], output_path, progress_cb)
