"""
FastAPI 应用入口。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger


# 统一把项目根目录加入导入路径，兼容直接运行和包内运行两种方式。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from src.core.config import get_config_manager
except ImportError:
    from core.config import get_config_manager

try:
    from src.core.logger import LoggerSetup
except ImportError:
    from core.logger import LoggerSetup

try:
    from src.core.middleware import TimeoutMiddleware
except ImportError:
    from core.middleware import TimeoutMiddleware

try:
    from src.api.routes import router
except ImportError:
    from api.routes import router


LoggerSetup.setup()

config_manager = get_config_manager()
api_config = config_manager.get_api_config()
system_config = config_manager.get_system_config()

app = FastAPI(
    title="PrivLexa — Privacy Policy Intelligence Platform",
    description=(
        "Multi-agent platform for privacy policy generation, conflict detection, "
        "compliance review, and readability assessment."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimeoutMiddleware, timeout_seconds=system_config.timeout)
app.include_router(router)

# 优先挂载已构建好的静态前端，便于单进程联调。
frontend_candidates = [
    PROJECT_ROOT / "frontend" / "build",
    PROJECT_ROOT / "frontend" / "privacy-policy-ai" / "out",
]
for frontend_build_dir in frontend_candidates:
    if frontend_build_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_build_dir), html=True), name="frontend")
        logger.info(f"已挂载静态前端目录: {frontend_build_dir}")
        break


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("PrivLexa 隐律智策平台启动中")
    logger.info(f"API 文档地址: http://localhost:{api_config.port}/docs")
    logger.info("前端地址: http://localhost:3000")
    logger.info(f"请求超时时间: {system_config.timeout} 秒")
    logger.info(f"日志文件: {system_config.log_file}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 60)
    logger.info("PrivLexa 隐律智策平台正在关闭")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=api_config.host,
        port=api_config.port,
        reload=api_config.reload,
        log_level=api_config.log_level,
    )
