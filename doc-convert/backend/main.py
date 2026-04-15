import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobs import init_db, cleanup_expired
from routers import convert


# 后台清理任务
cleanup_task = None


async def periodic_cleanup():
    """每小时清理一次过期文件"""
    while True:
        await asyncio.sleep(3600)  # 1 小时
        try:
            cleanup_expired()
        except Exception as e:
            print(f"Cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cleanup_task
    init_db()
    cleanup_expired()  # 启动时清理一次

    # 启动后台清理任务
    cleanup_task = asyncio.create_task(periodic_cleanup())

    yield

    # 关闭时取消任务
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="OpenConvert API",
    version="1.0.0",
    root_path="/doc-convert",
    lifespan=lifespan,
)

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(convert.router, prefix="/api")


@app.get("/api/health")
async def health():
    import shutil
    lo_ok = shutil.which("libreoffice") is not None
    tess_ok = shutil.which("tesseract") is not None
    return {"status": "ok", "libreoffice": lo_ok, "tesseract": tess_ok}
