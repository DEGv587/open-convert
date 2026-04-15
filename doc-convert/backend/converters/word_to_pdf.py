import os
from utils import libreoffice_convert


def convert(input_path: str, output_path: str, progress_cb=None):
    if progress_cb:
        progress_cb(10, "正在转换...")
    work_dir = os.path.dirname(output_path)
    result = libreoffice_convert(input_path, work_dir, "pdf")
    # 重命名到期望路径
    if result != output_path and os.path.exists(result):
        os.rename(result, output_path)
    if progress_cb:
        progress_cb(100)
