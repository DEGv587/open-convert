"""
格式映射和转换矩阵配置
"""

# 格式规范化映射（将别名统一为标准格式）
FORMAT_ALIASES = {
    "jpg": "jpg",
    "jpeg": "jpg",
    "png": "png",
    "pdf": "pdf",
    "docx": "docx",
    "doc": "docx",
    "pptx": "pptx",
    "ppt": "pptx",
    "heic": "heic",
}

# 格式显示名称
FORMAT_LABELS = {
    "pdf": "PDF",
    "docx": "Word (DOCX)",
    "pptx": "PPT (PPTX)",
    "png": "PNG",
    "jpg": "JPG",
}

# 转换矩阵：from_format -> [to_format, ...]
CONVERSION_MATRIX = {
    "pdf": ["docx", "pptx", "png", "jpg"],
    "docx": ["pdf", "pptx", "png", "jpg"],
    "pptx": ["pdf", "docx", "png", "jpg"],
    "jpg": ["pdf", "docx"],
    "png": ["pdf", "docx"],
    "heic": ["pdf", "docx"],
}


def normalize_format(fmt: str) -> str:
    """规范化格式名称"""
    return FORMAT_ALIASES.get(fmt.lower(), fmt.lower())


def get_supported_targets(from_fmt: str) -> list[str]:
    """获取指定格式支持的目标格式列表"""
    normalized = normalize_format(from_fmt)
    return CONVERSION_MATRIX.get(normalized, [])


def is_conversion_supported(from_fmt: str, to_fmt: str) -> bool:
    """检查是否支持指定的转换"""
    from_normalized = normalize_format(from_fmt)
    to_normalized = normalize_format(to_fmt)
    return to_normalized in CONVERSION_MATRIX.get(from_normalized, [])
