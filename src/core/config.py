"""
应用配置管理。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field, field_validator

try:
    from src.core.exceptions import ConfigurationError
except ImportError:
    from ..core.exceptions import ConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "configs.yaml"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

MODEL_API_KEY_ENV_VARS = (
    "MODEL_API_KEY",
    "QWEN_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
)

load_dotenv(dotenv_path=DEFAULT_ENV_PATH, override=False)


def _is_placeholder_env_value(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {
        "your-api-key-here",
        "your-model-api-key-here",
        "your-qwen-api-key-here",
        "your-deepseek-api-key-here",
        "your-dashscope-api-key-here",
        "changeme",
    }


def _get_first_non_empty_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _get_first_real_env(*names: str) -> Optional[tuple[str, str]]:
    for name in names:
        value = os.getenv(name)
        if value and value.strip() and not _is_placeholder_env_value(value):
            return name, value.strip()
    return None


class QwenClientConfig(BaseModel):
    api_key: str = Field(..., description="Model API key")
    base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Model API base URL",
    )
    model: str = Field(default="qwen-turbo", description="Model name")
    max_tokens: int = Field(default=8000, ge=1, le=100000, description="Maximum output tokens")
    timeout_seconds: int = Field(default=90, ge=5, le=600, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum chat retries for transient failures")
    retry_backoff_seconds: float = Field(default=1.5, ge=0.1, le=30.0, description="Base retry backoff in seconds")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("API Key 不能为空")
        return value.strip()


class APIConfig(BaseModel):
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8001, ge=1, le=65535, description="Bind port")
    reload: bool = Field(default=False, description="Enable auto reload")
    log_level: str = Field(default="info", description="Application log level")


class SystemConfig(BaseModel):
    max_round: int = Field(default=10, ge=1, description="Maximum agent interaction rounds")
    timeout: int = Field(default=300, ge=1, description="Request timeout in seconds")
    enable_logging: bool = Field(default=True, description="Enable file logging")
    log_file: str = Field(default="logs/agent_system.log", description="Primary log file path")


class AgentConfig(BaseModel):
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    system_message: str = Field(..., description="Agent system prompt")
    human_input_mode: str = Field(default="NEVER", description="Human input mode")
    max_consecutive_auto_reply: int = Field(default=3, ge=1, description="Maximum auto replies")


class AppConfig(BaseModel):
    qwen_client: QwenClientConfig
    api: APIConfig = Field(default_factory=APIConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    agents: Dict[str, AgentConfig] = Field(default_factory=dict)
    retrieval: Dict[str, Any] = Field(default_factory=dict)


class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    _config: Optional[AppConfig] = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self) -> None:
        try:
            logger.info("开始加载应用配置")
            config_file = self._get_config_file_path()

            if not os.path.exists(config_file):
                raise ConfigurationError(
                    f"配置文件不存在: {config_file}",
                    details={"config_file": config_file},
                )

            with open(config_file, "r", encoding="utf-8") as handle:
                config_dict = yaml.safe_load(handle) or {}

            self._apply_env_overrides(config_dict)

            if not config_dict["qwen_client"].get("api_key"):
                raise ConfigurationError(
                    "缺少 qwen_client.api_key，请设置 MODEL_API_KEY、QWEN_API_KEY、DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY",
                    details={
                        "required_env_vars": list(MODEL_API_KEY_ENV_VARS),
                        "config_file": config_file,
                    },
                )

            self._config = AppConfig(**config_dict)
            logger.info(f"配置加载完成，来源文件: {config_file}")
        except ConfigurationError:
            raise
        except Exception as exc:
            logger.error(f"加载配置失败: {exc}")
            raise ConfigurationError(
                f"加载配置失败: {exc}",
                details={"error": str(exc), "error_type": type(exc).__name__},
            )

    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> None:
        qwen_client = config_dict.setdefault("qwen_client", {})
        applied: Dict[str, str] = {}

        api_key_entry = _get_first_real_env(*MODEL_API_KEY_ENV_VARS)
        active_api_env = api_key_entry[0] if api_key_entry else None
        if api_key_entry:
            qwen_client["api_key"] = api_key_entry[1]
            applied["api_key"] = active_api_env or "env"

        base_url = None
        model_name = None
        max_tokens = _get_first_non_empty_env("MODEL_MAX_TOKENS")
        timeout_seconds = _get_first_non_empty_env("MODEL_TIMEOUT_SECONDS")
        max_retries = _get_first_non_empty_env("MODEL_MAX_RETRIES")
        retry_backoff_seconds = _get_first_non_empty_env("MODEL_RETRY_BACKOFF_SECONDS")

        if active_api_env == "MODEL_API_KEY":
            base_url = _get_first_non_empty_env("MODEL_BASE_URL")
            model_name = _get_first_non_empty_env("MODEL_NAME")
        elif active_api_env in {"QWEN_API_KEY", "DASHSCOPE_API_KEY"}:
            base_url = _get_first_non_empty_env("QWEN_BASE_URL", "DASHSCOPE_BASE_URL")
            model_name = _get_first_non_empty_env("QWEN_MODEL", "DASHSCOPE_MODEL")
            max_tokens = max_tokens or _get_first_non_empty_env("QWEN_MAX_TOKENS", "DASHSCOPE_MAX_TOKENS")
            timeout_seconds = timeout_seconds or _get_first_non_empty_env("QWEN_TIMEOUT_SECONDS", "DASHSCOPE_TIMEOUT_SECONDS")
            max_retries = max_retries or _get_first_non_empty_env("QWEN_MAX_RETRIES", "DASHSCOPE_MAX_RETRIES")
            retry_backoff_seconds = retry_backoff_seconds or _get_first_non_empty_env(
                "QWEN_RETRY_BACKOFF_SECONDS",
                "DASHSCOPE_RETRY_BACKOFF_SECONDS",
            )
        elif active_api_env == "DEEPSEEK_API_KEY":
            base_url = _get_first_non_empty_env("DEEPSEEK_BASE_URL")
            model_name = _get_first_non_empty_env("DEEPSEEK_MODEL")
            max_tokens = max_tokens or _get_first_non_empty_env("DEEPSEEK_MAX_TOKENS")
            timeout_seconds = timeout_seconds or _get_first_non_empty_env("DEEPSEEK_TIMEOUT_SECONDS")
            max_retries = max_retries or _get_first_non_empty_env("DEEPSEEK_MAX_RETRIES")
            retry_backoff_seconds = retry_backoff_seconds or _get_first_non_empty_env("DEEPSEEK_RETRY_BACKOFF_SECONDS")

        if not base_url:
            base_url = _get_first_non_empty_env("MODEL_BASE_URL")
        if base_url:
            qwen_client["base_url"] = base_url
            applied["base_url"] = "env"

        if not model_name:
            model_name = _get_first_non_empty_env("MODEL_NAME")
        if model_name:
            qwen_client["model"] = model_name
            applied["model"] = "env"

        if max_tokens:
            try:
                qwen_client["max_tokens"] = int(max_tokens)
                applied["max_tokens"] = "env"
            except ValueError:
                logger.warning(f"忽略无效的 MODEL_MAX_TOKENS 配置: {max_tokens}")

        if timeout_seconds:
            try:
                qwen_client["timeout_seconds"] = int(timeout_seconds)
                applied["timeout_seconds"] = "env"
            except ValueError:
                logger.warning(f"忽略无效的 MODEL_TIMEOUT_SECONDS 配置: {timeout_seconds}")

        if max_retries:
            try:
                qwen_client["max_retries"] = int(max_retries)
                applied["max_retries"] = "env"
            except ValueError:
                logger.warning(f"忽略无效的 MODEL_MAX_RETRIES 配置: {max_retries}")

        if retry_backoff_seconds:
            try:
                qwen_client["retry_backoff_seconds"] = float(retry_backoff_seconds)
                applied["retry_backoff_seconds"] = "env"
            except ValueError:
                logger.warning(
                    f"忽略无效的 MODEL_RETRY_BACKOFF_SECONDS 配置: {retry_backoff_seconds}"
                )

        if applied:
            logger.info(
                "检测到环境变量覆盖模型配置: "
                + ", ".join(sorted(applied.keys()))
            )

    @staticmethod
    def _get_config_file_path() -> str:
        config_path = os.getenv("CONFIG_PATH")
        if config_path:
            return config_path

        return str(DEFAULT_CONFIG_PATH)

    def get_config(self) -> AppConfig:
        if self._config is None:
            self._load_config()
        return self._config

    def get_dict(self) -> Dict[str, Any]:
        return self.get_config().model_dump()

    def get_qwen_config(self) -> QwenClientConfig:
        return self.get_config().qwen_client

    def get_api_config(self) -> APIConfig:
        return self.get_config().api

    def get_system_config(self) -> SystemConfig:
        return self.get_config().system

    def reload(self) -> None:
        logger.info("开始重新加载应用配置")
        self._config = None
        self._load_config()

config_manager: Optional[ConfigManager] = None


def get_config() -> Dict[str, Any]:
    return get_config_manager().get_dict()


def get_config_manager() -> ConfigManager:
    global config_manager
    if config_manager is None:
        config_manager = ConfigManager()
    return config_manager
