import asyncio
import json
import os
import uuid
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.datastructures import FormData, UploadFile

import jobs
from jobs import cleanup_expired, create_job, get_job, update_job
from converters import get_converter
from utils import temp_dir, convert_heic_to_jpeg
from formats import normalize_format, is_conversion_supported, CONVERSION_MATRIX, FORMAT_LABELS

router = APIRouter()

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
MAX_MULTI_FILES = int(os.getenv("MAX_MULTI_FILES", "50"))
_semaphore = asyncio.Semaphore(5)


@router.get("/config")
async def get_config():
    """返回前端配置"""
    return {
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "max_multi_files": MAX_MULTI_FILES,
        "conversion_matrix": CONVERSION_MATRIX,
        "format_labels": FORMAT_LABELS,
    }


def _get_ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()


def _as_upload(value: Any) -> Optional[UploadFile]:
    return value if isinstance(value, UploadFile) else None


def _extract_uploads(form: FormData) -> tuple[Optional[UploadFile], list[UploadFile]]:
    single_file = _as_upload(form.get("file"))
    multi_files = [_file for _file in (_as_upload(item) for item in form.getlist("files")) if _file is not None]
    return single_file, multi_files


async def _run_conversion(job_id: str, input_paths: list[str], from_fmt: str, to_fmt: str):
    if not _semaphore._value:
        update_job(job_id, status="error", error="Server busy. Max 5 concurrent conversions.")
        return

    async with _semaphore:
        update_job(job_id, status="processing", progress=0)
        try:
            converter = get_converter(from_fmt, to_fmt)
            work_dir = temp_dir(job_id)

            # HEIC 后端兜底：转换为 JPEG
            normalized_paths = []
            for p in input_paths:
                if p.lower().endswith(".heic"):
                    normalized_paths.append(convert_heic_to_jpeg(p))
                else:
                    normalized_paths.append(p)

            out_filename_base = os.path.splitext(os.path.basename(normalized_paths[0]))[0]
            if to_fmt in ("png", "jpg") and from_fmt in ("pdf", "docx", "pptx"):
                out_ext = "zip"
            else:
                out_ext = to_fmt
            output_path = os.path.join(work_dir, f"{out_filename_base}_converted.{out_ext}")

            def progress_cb(pct: int, stage: str = ""):
                update_job(job_id, progress=pct, stage=stage)

            loop = asyncio.get_event_loop()
            if len(normalized_paths) == 1:
                await loop.run_in_executor(
                    None,
                    lambda: converter(normalized_paths[0], output_path, progress_cb),
                )
            else:
                await loop.run_in_executor(
                    None,
                    lambda: converter(normalized_paths, output_path, progress_cb),
                )

            filename = os.path.basename(output_path)
            update_job(job_id, status="done", output_path=output_path, filename=filename, progress=100)
        except Exception as e:
            update_job(job_id, status="error", error=str(e))


@router.post("/convert")
async def convert(
    request: Request,
    background_tasks: BackgroundTasks,
):
    if not _semaphore._value:
        raise HTTPException(503, "Server busy. Max 5 concurrent conversions. Please retry shortly.")

    form = await request.form()
    to_format = str(form.get("to_format") or "").strip()
    file_order = form.get("file_order")
    file, files = _extract_uploads(form)

    if not to_format:
        raise HTTPException(400, "to_format is required")
    if file_order is not None and not isinstance(file_order, str):
        raise HTTPException(400, "file_order must be a string")

    to_fmt = to_format.lower().strip(".")

    # 单文件模式
    if file is not None and len(files) == 0:
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB.")
        from_fmt = normalize_format(_get_ext(file.filename))

        if not is_conversion_supported(from_fmt, to_fmt):
            raise HTTPException(400, f"Unsupported conversion: {from_fmt} -> {to_fmt} is not available")

        converter = get_converter(from_fmt, to_fmt)
        if converter is None:
            raise HTTPException(400, f"Unsupported conversion: {from_fmt} -> {to_fmt} is not available")

        job_id = str(uuid.uuid4())
        create_job(job_id)
        work_dir = temp_dir(job_id)
        save_path = os.path.join(work_dir, file.filename)
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        background_tasks.add_task(_run_conversion, job_id, [save_path], from_fmt, to_fmt)
        return {"job_id": job_id, "status": "pending", "from_format": from_fmt, "to_format": to_fmt}

    # 多文件模式（Image → PDF）
    if len(files) > 0:
        if len(files) > MAX_MULTI_FILES:
            raise HTTPException(400, f"Too many files. Maximum is {MAX_MULTI_FILES} images per batch.")
        if file_order is None:
            raise HTTPException(400, "file_order is required for multi-file upload")
        try:
            order: list[str] = json.loads(file_order)
        except Exception:
            raise HTTPException(400, "file_order must be a valid JSON array of filenames")
        if not isinstance(order, list) or not all(isinstance(name, str) for name in order):
            raise HTTPException(400, "file_order must be a valid JSON array of filenames")

        uploaded_names = {f.filename for f in files}
        order_names = set(order)
        for n in order_names:
            if n not in uploaded_names:
                raise HTTPException(400, f"file_order contains unknown filename: {n}")
        for n in uploaded_names:
            if n not in order_names:
                raise HTTPException(400, f"uploaded file not listed in file_order: {n}")

        from_fmt = "image"
        converter = get_converter("image", to_fmt)
        if converter is None:
            raise HTTPException(400, f"Unsupported conversion: image -> {to_fmt} is not available")

        job_id = str(uuid.uuid4())
        create_job(job_id)
        work_dir = temp_dir(job_id)

        saved: dict[str, str] = {}
        for f in files:
            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(400, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB.")
            save_path = os.path.join(work_dir, f.filename)
            with open(save_path, "wb") as fp:
                fp.write(content)
            saved[f.filename] = save_path

        ordered_paths = [saved[name] for name in order]
        background_tasks.add_task(_run_conversion, job_id, ordered_paths, "image", to_fmt)
        return {"job_id": job_id, "status": "pending", "from_format": "image", "to_format": to_fmt}

    raise HTTPException(400, "No file uploaded")


@router.get("/status/{job_id}")
async def status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found or expired")
    resp = {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"] or 0,
    }
    if job["stage"]:
        resp["stage"] = job["stage"]
    if job["status"] == "done":
        resp["filename"] = job["filename"]
    if job["status"] == "error":
        resp["error"] = job["error"]
    return resp


@router.get("/download/{job_id}")
async def download(job_id: str):
    job = get_job(job_id)
    if job is None or job["status"] != "done":
        raise HTTPException(404, "Job not found or not completed")
    output_path = job["output_path"]
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(404, "Output file no longer exists")
    return FileResponse(
        output_path,
        filename=job["filename"],
        media_type="application/octet-stream",
    )
