from pdf2docx import Converter


def convert(input_path: str, output_path: str, progress_cb=None):
    cv = Converter(input_path)
    total = len(cv.pages)

    def _page_cb(page_num, *args, **kwargs):
        if progress_cb and total:
            pct = int(page_num / total * 100)
            progress_cb(pct, f"第 {page_num}/{total} 页")

    cv.convert(output_path, start=0, end=None)
    cv.close()
    if progress_cb:
        progress_cb(100)
