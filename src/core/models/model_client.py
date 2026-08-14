"""
模型客户端工厂。
"""

from __future__ import annotations

from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient

try:
    from src.utils.utils import get_config
except ImportError:
    from ...utils.utils import get_config


class ModelClientFactory:
    @staticmethod
    def create_client(model_name: str):
        config = get_config() or {}
        qwen_config = dict(config.get("qwen_client") or {})
        if not qwen_config:
            raise ValueError("缺少 qwen_client 配置")

        max_tokens = qwen_config.pop("max_tokens", 16000)
        qwen_config.pop("model", None)
        qwen_config.pop("timeout_seconds", None)
        qwen_config.pop("max_retries", None)
        qwen_config.pop("retry_backoff_seconds", None)
        base_url = qwen_config.get("base_url")
        if isinstance(base_url, str):
            normalized_base_url = base_url.strip().rstrip("/")
            if "api.deepseek.com" in normalized_base_url and not normalized_base_url.endswith("/v1"):
                qwen_config["base_url"] = f"{normalized_base_url}/v1"

        return OpenAIChatCompletionClient(
            model=model_name,
            max_tokens=max_tokens,
            temperature=0.1,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": False,
                "structured_output": True,
                "family": ModelFamily.UNKNOWN,
            },
            **qwen_config,
        )
