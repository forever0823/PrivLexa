"""
应用健康检查。
"""

from __future__ import annotations

from typing import Any, Dict

from loguru import logger

try:
    from src.core.config import get_config_manager
except ImportError:
    from .config import get_config_manager

try:
    from src.core.factory_manager import get_agent_factory_manager
except ImportError:
    from .factory_manager import get_agent_factory_manager


class HealthCheckService:
    VERSION = "1.0.0"

    @staticmethod
    async def check_health() -> Dict[str, Any]:
        checks = {
            "config": await HealthCheckService._check_config(),
            "factory": await HealthCheckService._check_factory(),
        }
        status = "healthy" if all(check.get("passed", False) for check in checks.values()) else "degraded"
        return {
            "status": status,
            "version": HealthCheckService.VERSION,
            "checks": checks,
        }

    @staticmethod
    async def _check_config() -> Dict[str, Any]:
        try:
            config = get_config_manager().get_config()
            required_fields = ["qwen_client", "api", "system"]
            dumped = config.model_dump()
            missing_fields = [field for field in required_fields if field not in dumped]
            if missing_fields:
                return {
                    "passed": False,
                    "message": f"缺少配置字段: {', '.join(missing_fields)}",
                }

            api_key = config.qwen_client.api_key
            if not api_key or not api_key.strip():
                return {
                    "passed": False,
                    "message": "未配置模型 API Key",
                }

            return {
                "passed": True,
                "message": "配置检查通过",
            }
        except Exception as exc:
            logger.error(f"配置健康检查失败: {exc}")
            return {
                "passed": False,
                "message": f"配置检查失败: {exc}",
            }

    @staticmethod
    async def _check_factory() -> Dict[str, Any]:
        try:
            factory = get_agent_factory_manager().get_factory()
            if factory is None:
                return {
                    "passed": False,
                    "message": "Agent 工厂尚未初始化",
                }

            available_agents = await factory.get_available_agents()
            return {
                "passed": len(available_agents) > 0,
                "message": f"Agent 工厂可用，当前 Agent 数量: {len(available_agents)}",
                "agents_count": len(available_agents),
            }
        except Exception as exc:
            logger.error(f"Agent 工厂健康检查失败: {exc}")
            return {
                "passed": False,
                "message": f"Agent 工厂检查失败: {exc}",
            }
