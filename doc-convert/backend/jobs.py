import sqlite3
import os
import shutil
import time
from typing import Optional
from threading import Lock

DB_PATH = "/tmp/docconv/jobs.db"
TMP_BASE = "/tmp/docconv"
TTL_HOURS = int(os.getenv("JOB_TTL_HOURS", "1"))

# 数据库连接单例
_db_conn = None
_db_lock = Lock()


def _conn():
    """获取数据库连接（单例模式）"""
    global _db_conn
    if _db_conn is None:
        with _db_lock:
            if _db_conn is None:
                os.makedirs(TMP_BASE, exist_ok=True)
                _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                _db_conn.row_factory = sqlite3.Row
    return _db_conn


def init_db():
    os.makedirs(TMP_BASE, exist_ok=True)
    conn = _conn()
    with _db_lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                output_path TEXT,
                filename TEXT,
                error TEXT,
                progress INTEGER DEFAULT 0,
                stage TEXT,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()


def create_job(job_id: str):
    conn = _conn()
    with _db_lock:
        conn.execute(
            "INSERT INTO jobs (job_id, status, progress, created_at) VALUES (?, 'pending', 0, ?)",
            (job_id, time.time()),
        )
        conn.commit()


def update_job(
    job_id: str,
    status: Optional[str] = None,
    output_path: Optional[str] = None,
    filename: Optional[str] = None,
    error: Optional[str] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
):
    fields = []
    values = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if output_path is not None:
        fields.append("output_path = ?")
        values.append(output_path)
    if filename is not None:
        fields.append("filename = ?")
        values.append(filename)
    if error is not None:
        fields.append("error = ?")
        values.append(error)
    if progress is not None:
        fields.append("progress = ?")
        values.append(progress)
    if stage is not None:
        fields.append("stage = ?")
        values.append(stage)
    if not fields:
        return
    values.append(job_id)
    conn = _conn()
    with _db_lock:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?", values)
        conn.commit()


def get_job(job_id: str) -> Optional[dict]:
    conn = _conn()
    with _db_lock:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def cleanup_expired():
    cutoff = time.time() - TTL_HOURS * 3600
    # 清理文件系统
    if os.path.isdir(TMP_BASE):
        for name in os.listdir(TMP_BASE):
            if name == "jobs.db":
                continue
            path = os.path.join(TMP_BASE, name)
            if os.path.isdir(path):
                try:
                    mtime = os.path.getmtime(path)
                    if mtime < cutoff:
                        shutil.rmtree(path, ignore_errors=True)
                except OSError:
                    pass
    # 清理数据库
    conn = _conn()
    with _db_lock:
        conn.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))
        conn.commit()
