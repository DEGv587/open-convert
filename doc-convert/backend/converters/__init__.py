from typing import Callable, Optional


def get_converter(from_fmt: str, to_fmt: str) -> Optional[Callable]:
    from_fmt = from_fmt.lower()
    to_fmt = to_fmt.lower()

    mapping = {
        ("pdf", "docx"): _import("pdf_to_word", "convert"),
        ("pdf", "pptx"): _import("pdf_to_ppt", "convert"),
        ("pdf", "png"): _import("pdf_to_image", "convert_png"),
        ("pdf", "jpg"): _import("pdf_to_image", "convert_jpg"),
        ("docx", "pdf"): _import("word_to_pdf", "convert"),
        ("docx", "pptx"): _import("word_to_ppt", "convert"),
        ("docx", "png"): _import("word_to_image", "convert_png"),
        ("docx", "jpg"): _import("word_to_image", "convert_jpg"),
        ("pptx", "pdf"): _import("ppt_to_pdf", "convert"),
        ("pptx", "docx"): _import("ppt_to_word", "convert"),
        ("pptx", "png"): _import("ppt_to_image", "convert_png"),
        ("pptx", "jpg"): _import("ppt_to_image", "convert_jpg"),
        ("image", "pdf"): _import("image_to_pdf", "convert"),
        ("jpg", "pdf"): _import("image_to_pdf", "convert_single"),
        ("png", "pdf"): _import("image_to_pdf", "convert_single"),
        ("heic", "pdf"): _import("image_to_pdf", "convert_single"),
        ("jpg", "docx"): _import("image_to_word", "convert"),
        ("png", "docx"): _import("image_to_word", "convert"),
        ("heic", "docx"): _import("image_to_word", "convert"),
    }
    return mapping.get((from_fmt, to_fmt))


def _import(module_name: str, func_name: str) -> Callable:
    import importlib
    mod = importlib.import_module(f"converters.{module_name}")
    return getattr(mod, func_name)
