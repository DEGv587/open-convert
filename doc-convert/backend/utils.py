import os
import shutil
import subprocess
import tempfile


TMP_BASE = "/tmp/docconv"
LIBREOFFICE_TIMEOUT = 90


def temp_dir(job_id: str) -> str:
    path = os.path.join(TMP_BASE, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def cleanup(path: str):
    if path and os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)


def convert_heic_to_jpeg(input_path: str, quality: int = 92) -> str:
    """
    将 HEIC 文件转换为 JPEG。
    返回输出文件路径。
    """
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    output_path = input_path.rsplit('.', 1)[0] + '.jpg'

    img = Image.open(input_path)
    img.save(output_path, "JPEG", quality=quality)

    return output_path


def libreoffice_convert(input_path: str, output_dir: str, to_format: str) -> str:
    """
    使用 LibreOffice headless 将文件转换为指定格式。
    返回输出文件的路径。
    """
    cmd = [
        "libreoffice",
        "--headless",
        "--norestore",
        "--nofirststartwizard",
        "--convert-to", to_format,
        "--outdir", output_dir,
        input_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            timeout=LIBREOFFICE_TIMEOUT,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"LibreOffice conversion timed out after {LIBREOFFICE_TIMEOUT}s")

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr.strip()}")

    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base}.{to_format}")
    if not os.path.exists(output_path):
        # 有些格式 LibreOffice 输出扩展名可能不同
        candidates = [f for f in os.listdir(output_dir) if f.startswith(base)]
        if candidates:
            output_path = os.path.join(output_dir, candidates[0])
        else:
            raise RuntimeError(f"LibreOffice output file not found in {output_dir}")

    return output_path
