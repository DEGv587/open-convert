import os
import cv2
import numpy as np
import pytesseract
from docx import Document
from docx.shared import Inches
from PIL import Image


def _preprocess(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # 二值化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def convert(input_path: str, output_path: str, progress_cb=None):
    if progress_cb:
        progress_cb(5, "预处理图片...")

    img = cv2.imread(input_path)
    if img is None:
        # 尝试用 PIL 读取（兼容更多格式）
        pil_img = Image.open(input_path).convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    processed = _preprocess(img)
    if progress_cb:
        progress_cb(20, "OCR 识别中...")

    text = pytesseract.image_to_string(
        processed,
        lang="eng+chi_sim",
        config="--psm 6",
    )
    if progress_cb:
        progress_cb(80, "生成文档...")

    doc = Document()
    for para in text.split("\n"):
        if para.strip():
            doc.add_paragraph(para)

    doc.save(output_path)
    if progress_cb:
        progress_cb(100)
