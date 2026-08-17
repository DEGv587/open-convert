from typing import Callable, Optional


def get_converter(from_fmt: str, to_fmt: str, translate_to: Optional[str] = None) -> Optional[Callable]:
    """
    获取转换器

    Args:
        from_fmt: 源格式
        to_fmt: 目标格式
        translate_to: 翻译目标语言（'zh' | 'en'），仅用于 PDF→Word

    Returns:
        转换函数
    """
    from_fmt = from_fmt.lower()
    to_fmt = to_fmt.lower()

    # PDF → PDF 带翻译（图片叠加模式，保留原格式）
    if from_fmt == "pdf" and to_fmt == "pdf" and translate_to:
        return _import("pdf_to_pdf_translate", "convert")

    # PDF → Word 带翻译（图片叠加模式）
    if from_fmt == "pdf" and to_fmt == "docx" and translate_to:
        return _import("pdf_to_word_translate_image_overlay", "convert")

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
        ("image", "docx"): _import("image_to_word", "convert"),
        ("jpg", "pdf"): _import("image_to_pdf", "convert_single"),
        ("png", "pdf"): _import("image_to_pdf", "convert_single"),
        ("heic", "pdf"): _import("image_to_pdf", "convert_single"),
        ("jpg", "docx"): _import("image_to_word", "convert"),
        ("png", "docx"): _import("image_to_word", "convert"),
        ("heic", "docx"): _import("image_to_word", "convert"),
        ("text", "docx"): _import("text_to_word", "convert"),
        ("text", "pdf"): _import("text_to_pdf", "convert"),
    }
    return mapping.get((from_fmt, to_fmt))


def _import(module_name: str, func_name: str) -> Callable:
    import importlib
    mod = importlib.import_module(f"converters.{module_name}")
    return getattr(mod, func_name)
