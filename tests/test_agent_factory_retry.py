from __future__ import annotations

import sys
from pathlib import Path

import pytest

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.agent_factory import AgentFactory


class RemoteProtocolError(Exception):
    pass


class StatusCodeError(Exception):
    def __init__(self, status_code):
        super().__init__(f"http status {status_code}")
        self.status_code = status_code


class ResponseStatusError(Exception):
    def __init__(self, status_code):
        super().__init__("upstream response failed")
        self.response = type("Response", (), {"status_code": status_code})()


@pytest.fixture()
def factory():
    return AgentFactory.__new__(AgentFactory)


def wrap_with_cause(root_error: Exception, outer_message: str = "request wrapper") -> Exception:
    outer = Exception(outer_message)
    outer.__cause__ = root_error
    return outer


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            wrap_with_cause(RemoteProtocolError("socket closed unexpectedly")),
            id="根因类型命中可重试名单",
        ),
        pytest.param(
            wrap_with_cause(Exception("peer closed connection without sending complete message body")),
            id="根因消息命中可重试标记",
        ),
    ],
)
def test_retryable_chat_error_detects_retryable_exception_chain(factory, error):
    """可从异常链中识别需要重试的聊天错误"""
    assert factory._is_retryable_chat_error(error) is True


@pytest.mark.parametrize(
    "status_code",
    [
        pytest.param(408, id="408请求超时"),
        pytest.param(429, id="429频率限制"),
        pytest.param(503, id="503服务不可用"),
    ],
)
def test_retryable_chat_error_detects_retryable_status_code(factory, status_code):
    """可识别异常对象上的可重试状态码"""
    assert factory._is_retryable_chat_error(StatusCodeError(status_code)) is True


@pytest.mark.parametrize(
    "status_code",
    [
        pytest.param(409, id="409响应冲突"),
        pytest.param(504, id="504网关超时"),
    ],
)
def test_retryable_chat_error_detects_retryable_response_status_code(factory, status_code):
    """可识别响应对象上的可重试状态码"""
    assert factory._is_retryable_chat_error(ResponseStatusError(status_code)) is True


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ValueError("invalid prompt payload"), id="参数值错误"),
        pytest.param(StatusCodeError(400), id="400客户端错误"),
    ],
)
def test_retryable_chat_error_ignores_non_retryable_errors(factory, error):
    """不会把明显不可重试的错误误判为可重试"""
    assert factory._is_retryable_chat_error(error) is False
