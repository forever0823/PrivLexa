"""
请求超时中间件。
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: int = 300):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
        logger.info(f"超时中间件初始化完成，超时时间={timeout_seconds} 秒")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 在请求状态中记录链路 ID 和开始时间，便于日志定位慢请求。
        request_id = f"{time.time()}"
        request.state.request_id = request_id
        request.state.start_time = time.time()

        try:
            response = await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
            elapsed_time = time.time() - request.state.start_time
            if elapsed_time > 10:
                logger.warning(
                    f"[{request_id}] 慢请求告警: {elapsed_time:.2f}s {request.method} {request.url.path}"
                )
            else:
                logger.debug(
                    f"[{request_id}] 请求完成: {elapsed_time:.2f}s {request.method} {request.url.path}"
                )
            return response
        except asyncio.TimeoutError:
            logger.error(
                f"[{request_id}] 请求超时，耗时超过 {self.timeout_seconds} 秒: "
                f"{request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=504,
                content={"error_code": "TIMEOUT_ERROR", "message": "请求超时"},
            )
        except Exception as exc:
            elapsed_time = time.time() - request.state.start_time
            logger.error(
                f"[{request_id}] 请求失败，耗时 {elapsed_time:.2f} 秒: "
                f"{request.method} {request.url.path} - {exc}"
            )
            raise
