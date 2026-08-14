"""
线程安全的 AgentFactory 管理器。
"""

from __future__ import annotations

import threading
from typing import Optional

from loguru import logger

try:
    from src.agents.agent_factory import AgentFactory
except ImportError:
    from ..agents.agent_factory import AgentFactory


class AgentFactoryManager:
    _instance: Optional["AgentFactoryManager"] = None
    _lock = threading.Lock()
    _factory: Optional[AgentFactory] = None

    def __new__(cls) -> "AgentFactoryManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    logger.debug("已创建 AgentFactoryManager 单例")
        return cls._instance

    def get_factory(self) -> AgentFactory:
        if self._factory is None:
            with self._lock:
                if self._factory is None:
                    logger.info("开始创建共享 AgentFactory 实例")
                    self._factory = AgentFactory()
        return self._factory

    def reset_factory(self) -> None:
        with self._lock:
            if self._factory is not None:
                self._factory.clear_cache()
                self._factory = None
                logger.info("共享 AgentFactory 实例已重置")


_factory_manager = AgentFactoryManager()


def get_agent_factory_manager() -> AgentFactoryManager:
    return _factory_manager


def get_agent_factory() -> AgentFactory:
    return _factory_manager.get_factory()
