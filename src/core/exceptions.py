"""
自定义应用异常。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class PPGLLMException(Exception):
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(PPGLLMException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_ERROR", details)


class ModelClientError(PPGLLMException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MODEL_CLIENT_ERROR", details)


class AgentBuildError(PPGLLMException):
    def __init__(self, agent_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["agent_type"] = agent_type
        super().__init__(message, "AGENT_BUILD_ERROR", details)


class AgentExecutionError(PPGLLMException):
    def __init__(self, agent_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["agent_type"] = agent_type
        super().__init__(message, "AGENT_EXECUTION_ERROR", details)


class InvalidRequestError(PPGLLMException):
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, "INVALID_REQUEST", details)


class UnsupportedAgentTypeError(PPGLLMException):
    def __init__(self, agent_type: str, supported_types: Optional[list] = None):
        details = {"agent_type": agent_type}
        if supported_types:
            details["supported_types"] = supported_types
        super().__init__(f"不支持的 Agent 类型: {agent_type}", "UNSUPPORTED_AGENT_TYPE", details)


class TimeoutError(PPGLLMException):
    def __init__(self, operation: str, timeout_seconds: float, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["operation"] = operation
        details["timeout_seconds"] = timeout_seconds
        message = f"操作超时: {operation}（{timeout_seconds} 秒）"
        super().__init__(message, "TIMEOUT_ERROR", details)


class ExternalServiceError(PPGLLMException):
    def __init__(
        self,
        service_name: str,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        details["service_name"] = service_name
        if status_code is not None:
            details["status_code"] = status_code
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)


class MemoryError(PPGLLMException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MEMORY_ERROR", details)
