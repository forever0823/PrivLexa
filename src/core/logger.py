"""
日志初始化与辅助方法。
"""

from __future__ import annotations

import os
import sys

from loguru import logger

try:
    from src.core.config import get_config_manager
except ImportError:
    from .config import get_config_manager


class LoggerSetup:
    _initialized = False

    @classmethod
    def setup(cls) -> None:
        if cls._initialized:
            return

        logger.remove()
        logger.add(
            sys.stdout,
            level="DEBUG",
            format=(
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=sys.stdout.isatty() and os.environ.get("NO_COLOR") is None,
        )

        try:
            system_config = get_config_manager().get_system_config()
            if system_config.enable_logging:
                log_file = system_config.log_file
                log_dir = os.path.dirname(log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)

                # 主日志和错误日志分开落盘，便于排查服务问题。
                logger.add(
                    log_file,
                    level="INFO",
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                    rotation="10 MB",
                    retention="7 days",
                    encoding="utf-8",
                    delay=True,
                    errors="ignore",
                )

                error_log_file = log_file.replace(".log", "_error.log")
                logger.add(
                    error_log_file,
                    level="ERROR",
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                    rotation="10 MB",
                    retention="7 days",
                    encoding="utf-8",
                    delay=True,
                    errors="ignore",
                )

                logger.info(f"已启用文件日志: {log_file}")
                logger.info(f"已启用错误日志: {error_log_file}")
        except Exception as exc:
            logger.warning(f"文件日志初始化已跳过: {exc}")

        cls._initialized = True
        logger.info("日志系统初始化完成")


def get_logger(name: str):
    return logger.bind(component=name)
