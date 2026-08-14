"""
通用辅助函数。
"""

from __future__ import annotations

import os

from loguru import logger

try:
    from src.core.config import get_config as get_config_from_manager
except ImportError:
    from ..core.config import get_config as get_config_from_manager


def get_memory_dir() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(base_dir, "..", "memory"))


def get_config():
    try:
        return get_config_from_manager()
    except Exception as exc:
        logger.error(f"通过工具函数加载配置失败: {exc}")
        return {}


def get_log_dir() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs"))
