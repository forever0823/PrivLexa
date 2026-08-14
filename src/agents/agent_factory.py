"""
Agent 工厂：负责构建 Agent、复用缓存并转发 LLM 请求。
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import Any, Dict, List, Optional
import traceback

import httpx
from loguru import logger

try:
    from src.utils.utils import get_config
except ImportError:
    from ..utils.utils import get_config

try:
    from src.core.models.model_client import ModelClientFactory
except ImportError:
    from ..core.models.model_client import ModelClientFactory

try:
    from src.core.exceptions import (
        AgentBuildError,
        AgentExecutionError,
        ConfigurationError,
        ModelClientError,
        UnsupportedAgentTypeError,
    )
except ImportError:
    from ..core.exceptions import (
        AgentBuildError,
        AgentExecutionError,
        ConfigurationError,
        ModelClientError,
        UnsupportedAgentTypeError,
    )

from .compliance_checker_builder import ComplianceCheckerBuilder
from .compliance_checker_builder_multi_jurisdiction import ComplianceCheckerBuilder as ComplianceCheckerBuilderMulti
from .conflict_detector_builder import ConflictDetectorBuilder
from .multi_jurisdiction_coordinator_builder import MultiJurisdictionCoordinatorBuilder
from .privacy_policy_generator_builder import PrivacyPolicyGeneratorBuilder


AGENT_DESCRIPTIONS: Dict[str, str] = {
    "privacy_policy_generator": (
        "根据法域要求、法规知识图谱上下文和检索证据生成隐私政策。"
    ),
    "compliance_checker": (
        "针对单一法域审查隐私政策，并输出证据、法规映射和整改建议。"
    ),
    "conflict_detector": (
        "结合规则推理与语义相似度检测条款硬冲突与软冲突。"
    ),
    "compliance_checker_multi": (
        "并行执行中国、美国、欧盟多法域合规检测，并输出统一评估结论。"
    ),
    "multi_jurisdiction_coordinator": (
        "协调多法域下的生成、冲突检测和合规审查流程。"
    ),
}

AGENT_DESCRIPTIONS["privacy_policy_generator"] = (
    "面向目标法域生成隐私政策草案，约束条款只服务所选法域，并显式暴露缺失事实与待确认项。"
)

GENERATOR_FALLBACK_MESSAGE = "\n".join(
    [
        "你是目标法域隐私政策生成智能体。",
        "除非用户明确要求多法域协调版本，否则仅针对所选法域起草完整、审慎且可审计的隐私政策。",
        "将知识图谱、法规检索或确定性基线作为起草证据，缺失事实使用“[待确认：具体事实]”标注。",
        "除非用户明确指定其他语言，全文使用简体中文。",
    ]
)

COMPLIANCE_FALLBACK_MESSAGE = "\n".join(
    [
        "你是隐私政策合规审查专家。",
        "依据所选法域审查政策，并说明证据、差距、法律依据和整改措施。",
        "如提供确定性基线，应在其基础上深化分析，而不是忽略基线。",
        "除非用户明确指定其他语言，全文使用简体中文。",
    ]
)

CONFLICT_FALLBACK_MESSAGE = "\n".join(
    [
        "你是隐私政策条款冲突检测专家。",
        "结合规则硬约束与语义相似度进行混合分析。",
        "为每项冲突给出严重程度、证据、原因和整改建议。",
        "除非用户明确指定其他语言，全文使用简体中文。",
    ]
)

MULTI_COMPLIANCE_FALLBACK_MESSAGE = "\n".join(
    [
        "你是多法域隐私政策合规审查专家。",
        "先按各法域分别审查，再识别严格共同基线和仍然存在的冲突。",
        "将提供的确定性基线作为审查证据。",
        "除非用户明确指定其他语言，全文使用简体中文。",
    ]
)

COORDINATION_FALLBACK_MESSAGE = "\n".join(
    [
        "你是多法域隐私政策任务协调智能体。",
        "协调不同法域的政策生成、冲突检测和合规审查。",
        "输出清晰的执行计划、结果摘要和按优先级排序的后续行动。",
        "除非用户明确指定其他语言，全文使用简体中文。",
    ]
)


class AgentFactory:
    def __init__(self):
        self.model_client = self._create_model_client()
        self.agent_builders = {
            "privacy_policy_generator": PrivacyPolicyGeneratorBuilder,
            "compliance_checker": ComplianceCheckerBuilder,
            "conflict_detector": ConflictDetectorBuilder,
            "compliance_checker_multi": ComplianceCheckerBuilderMulti,
            "multi_jurisdiction_coordinator": MultiJurisdictionCoordinatorBuilder,
        }
        # 缓存已构建 Agent，减少重复初始化模型和提示词的开销。
        self._built_agents: Dict[str, Any] = {}
        self._cache_max_size = 100
        logger.info(f"Agent 工厂初始化完成，可用构建器: {list(self.agent_builders.keys())}")

    def _create_model_client(self):
        try:
            config = get_config() or {}
            qwen_config = config.get("qwen_client") or {}
            if not qwen_config:
                raise ConfigurationError(
                    "无法加载模型配置",
                    details={"reason": "缺少 qwen_client 配置"},
                )

            model_name = qwen_config.get("model", "qwen-turbo")
            logger.info(f"开始创建模型客户端: {model_name}")
            return ModelClientFactory.create_client(model_name=model_name)
        except ConfigurationError:
            raise
        except Exception as exc:
            logger.error(f"创建模型客户端失败: {exc}\n{traceback.format_exc()}")
            raise ModelClientError(
                message="创建模型客户端失败",
                details={"error": str(exc), "error_type": type(exc).__name__},
            )

    async def build_agent(self, agent_type: str, tools=None, memory_files=None, **kwargs):
        cache_key = self._build_cache_key(agent_type, tools, memory_files, kwargs)
        if cache_key in self._built_agents:
            logger.debug(f"命中 Agent 缓存: {agent_type}")
            return self._built_agents[cache_key]

        if agent_type not in self.agent_builders:
            raise UnsupportedAgentTypeError(
                agent_type=agent_type,
                supported_types=list(self.agent_builders.keys()),
            )

        try:
            if len(self._built_agents) >= self._cache_max_size:
                self._clean_oldest_cache()

            # 不同 Agent 类型在这里映射到不同 Builder，并注入运行参数。
            builder = self._create_builder(agent_type, tools, memory_files, kwargs)
            agent = await builder.build()
            self._built_agents[cache_key] = agent
            logger.info(f"Agent 构建完成: {agent_type}，当前缓存数量={len(self._built_agents)}")
            return agent
        except UnsupportedAgentTypeError:
            raise
        except Exception as exc:
            logger.error(f"构建 Agent 失败: {agent_type}，错误={exc}\n{traceback.format_exc()}")
            raise AgentBuildError(
                agent_type=agent_type,
                message=f"构建 Agent 失败: {agent_type}",
                details={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "tools_provided": tools is not None,
                    "memory_files_provided": memory_files is not None,
                },
            )

    def _create_builder(self, agent_type: str, tools, memory_files, kwargs: Dict[str, Any]):
        builder_class = self.agent_builders[agent_type]
        common = {
            "model_client": self.model_client,
            "tools": tools,
            "memory_files": memory_files,
        }
        if agent_type == "privacy_policy_generator":
            return builder_class(
                jurisdiction=kwargs.get("jurisdiction", "CN"),
                use_rag=kwargs.get("use_rag", False),
                **common,
            )
        if agent_type == "compliance_checker":
            selected_jurisdiction = kwargs.get("jurisdiction")
            if not selected_jurisdiction:
                selected_jurisdictions = kwargs.get("jurisdictions") or []
                selected_jurisdiction = selected_jurisdictions[0] if selected_jurisdictions else "CN"
            return builder_class(jurisdiction=selected_jurisdiction, **common)
        if agent_type == "conflict_detector":
            return builder_class(detection_mode=kwargs.get("detection_mode", "both"), **common)
        if agent_type == "compliance_checker_multi":
            return builder_class(
                jurisdictions=kwargs.get("jurisdictions", ["CN"]),
                parallel_execution=kwargs.get("parallel_execution", True),
                return_markdown=kwargs.get("return_markdown", False),
                **common,
            )
        if agent_type == "multi_jurisdiction_coordinator":
            return builder_class(
                operation=kwargs.get("operation", "full"),
                parallel_processing=kwargs.get("parallel_processing", True),
                **common,
            )
        return builder_class(**common)

    def _build_cache_key(self, agent_type: str, tools, memory_files, kwargs: Dict[str, Any]) -> str:
        ordered_kwargs = ",".join(f"{key}={kwargs[key]!r}" for key in sorted(kwargs))
        return f"{agent_type}|tools={id(tools)}|memory={id(memory_files)}|{ordered_kwargs}"

    async def get_agent_info(self, agent_type: str) -> Dict[str, Any]:
        if agent_type not in self.agent_builders:
            raise UnsupportedAgentTypeError(
                agent_type=agent_type,
                supported_types=list(self.agent_builders.keys()),
            )

        return {
            "type": agent_type,
            "name": agent_type.replace("_", " ").title(),
            "description": AGENT_DESCRIPTIONS.get(agent_type, ""),
            "status": "available",
        }

    async def get_available_agents(self) -> List[Dict[str, Any]]:
        agents: List[Dict[str, Any]] = []
        for agent_type in self.agent_builders:
            try:
                agents.append(await self.get_agent_info(agent_type))
            except Exception as exc:
                logger.error(f"获取 Agent 信息失败: {agent_type}，错误={exc}")
        return agents

    async def chat_with_agent(
        self,
        agent_type: str,
        message: str,
        tools: Optional[List] = None,
        memory_files: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            logger.info(f"收到 Agent 对话请求: agent_type={agent_type}, message_length={len(message)}")
            agent = await self.build_agent(agent_type, tools, memory_files, **kwargs)

            if agent_type == "privacy_policy_generator":
                response = await self._process_privacy_policy_request(agent, message)
            elif agent_type in {"compliance_checker", "compliance_checker_multi"}:
                response = await self._process_compliance_check_request(agent, message)
            elif agent_type == "conflict_detector":
                response = await self._process_conflict_detection_request(agent, message)
            elif agent_type == "multi_jurisdiction_coordinator":
                response = await self._process_coordination_request(agent, message)
            else:
                response = await self._default_process_request(agent, message)

            logger.info(f"Agent 响应完成: agent_type={agent_type}, response_length={len(response)}")
            return {
                "success": True,
                "agent_type": agent_type,
                "agent_name": getattr(agent, "name", agent_type),
                "response": response,
                "message": f"{agent_type} 执行完成",
            }
        except (AgentBuildError, AgentExecutionError, UnsupportedAgentTypeError):
            raise
        except Exception as exc:
            logger.error(f"Agent 对话失败: {agent_type}，错误={exc}\n{traceback.format_exc()}")
            raise AgentExecutionError(
                agent_type=agent_type,
                message=f"Agent 执行失败: {agent_type}",
                details={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "message_length": len(message) if message else 0,
                },
            )

    async def _process_privacy_policy_request(self, agent, message: str) -> str:
        return await self._send_chat_request(agent, message)

    async def _process_compliance_check_request(self, agent, message: str) -> str:
        return await self._send_chat_request(agent, message)

    async def _process_conflict_detection_request(self, agent, message: str) -> str:
        return await self._send_chat_request(agent, message)

    async def _process_coordination_request(self, agent, message: str) -> str:
        return await self._send_chat_request(agent, message)

    async def _default_process_request(self, agent, message: str) -> str:
        return await self._send_chat_request(agent, message)

    async def _send_chat_request(self, agent, message: str, uploaded_files=None) -> str:
        try:
            system_message = self._resolve_system_message(agent)
            user_message = self._build_user_message_with_files(message, uploaded_files)

            config = get_config() or {}
            qwen_config = dict(config.get("qwen_client") or {})
            api_key = qwen_config.get("api_key", "")
            base_url = self._normalize_base_url(
                qwen_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            )
            model = qwen_config.get("model", "qwen-turbo")
            max_tokens = self._resolve_max_tokens(
                qwen_config.get("max_tokens", 8000),
                getattr(agent, "_agent_type", getattr(agent, "name", "")),
            )
            timeout_seconds = qwen_config.get("timeout_seconds", 150)
            max_retries = qwen_config.get("max_retries", 1)
            retry_backoff_seconds = qwen_config.get("retry_backoff_seconds", 1.5)

            if not api_key:
                raise ConfigurationError("未配置模型 API Key")

            system_length = len(system_message)
            user_length = len(user_message)
            request_payload = self._build_chat_request_payload(
                model=model,
                system_message=system_message,
                user_message=user_message,
                max_tokens=max_tokens,
            )

            for attempt in range(max_retries + 1):
                try:
                    result = await asyncio.to_thread(
                        self._send_chat_request_once,
                        api_key,
                        base_url,
                        request_payload,
                        timeout_seconds,
                    )
                    if not result:
                        raise ValueError("模型返回内容为空")

                    self._validate_response_by_agent_type(result, agent)
                    return result
                except Exception as exc:
                    if not self._is_retryable_chat_error(exc) or attempt >= max_retries:
                        raise

                    backoff_seconds = retry_backoff_seconds * (2 ** attempt) + random.uniform(0, 0.25)
                    logger.warning(
                        "Chat request failed with a retryable error. "
                        f"attempt={attempt + 1}/{max_retries + 1}, "
                        f"model={model}, base_url={base_url}, error_type={type(exc).__name__}, "
                        f"system_chars={system_length}, user_chars={user_length}, "
                        f"retry_in={backoff_seconds:.2f}s"
                    )
                    await asyncio.sleep(backoff_seconds)
        except (ConfigurationError, AgentExecutionError):
            raise
        except Exception as exc:
            logger.error(f"发送对话请求失败: {exc}\n{traceback.format_exc()}")
            raise AgentExecutionError(
                agent_type=getattr(agent, "_agent_type", getattr(agent, "name", "unknown")),
                message="发送对话请求失败",
                details={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "operation": "_send_chat_request",
                    "model": model if "model" in locals() else None,
                    "base_url": base_url if "base_url" in locals() else None,
                    "timeout_seconds": timeout_seconds if "timeout_seconds" in locals() else None,
                },
            )

    @staticmethod
    def _build_chat_request_payload(
        model: str,
        system_message: str,
        user_message: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }

    @staticmethod
    def _resolve_max_tokens(configured_max_tokens: Any, agent_type: str) -> int:
        try:
            max_tokens = int(configured_max_tokens)
        except (TypeError, ValueError):
            max_tokens = 8000

        minimums = {
            "privacy_policy_generator": 8192,
            "multi_jurisdiction_coordinator": 8192,
            "compliance_checker_multi": 6144,
        }
        return max(max_tokens, minimums.get(agent_type, 0))

    def _send_chat_request_once(
        self,
        api_key: str,
        base_url: str,
        request_payload: Dict[str, Any],
        timeout_seconds: float,
    ) -> str:
        timeout = self._build_http_timeout(timeout_seconds)
        stream_payload = dict(request_payload)
        stream_payload["stream"] = True

        with httpx.Client(
            timeout=timeout,
            http2=False,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Connection": "close",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=1),
            trust_env=False,
        ) as http_client:
            with http_client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json=stream_payload,
            ) as response:
                response.raise_for_status()
                return self._read_chat_response(response)

    @staticmethod
    def _build_http_timeout(timeout_seconds: float) -> httpx.Timeout:
        read_timeout = float(timeout_seconds)
        return httpx.Timeout(
            connect=min(15.0, read_timeout),
            read=read_timeout,
            write=min(60.0, read_timeout),
            pool=min(15.0, read_timeout),
        )

    def _read_chat_response(self, response: httpx.Response) -> str:
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/event-stream" not in content_type:
            payload = response.json()
            result = self._extract_content_from_chat_payload(payload)
            if result:
                return result
            raise ValueError("模型返回内容为空")

        chunks: List[str] = []
        for line in response.iter_lines():
            if not line:
                continue

            normalized = line.decode("utf-8", errors="ignore") if isinstance(line, bytes) else line
            if not normalized.startswith("data:"):
                continue

            data = normalized[5:].strip()
            if not data:
                continue
            if data == "[DONE]":
                break

            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                logger.debug(f"忽略无法解析的流式事件: {data[:120]}")
                continue

            chunk = self._extract_content_from_chat_payload(event)
            if chunk:
                chunks.append(chunk)

        result = "".join(chunks).strip()
        if result:
            return result
        raise ValueError("模型返回内容为空")

    def _extract_content_from_chat_payload(self, payload: Dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""

        choice = choices[0] or {}
        delta = choice.get("delta") or {}
        message_payload = choice.get("message") or {}

        for candidate in (
            delta.get("content"),
            message_payload.get("content"),
        ):
            normalized = self._normalize_message_content(candidate)
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _normalize_message_content(content: Any) -> str:
        if isinstance(content, str):
            return AgentFactory._strip_model_reasoning(content)
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    sanitized = AgentFactory._strip_model_reasoning(item)
                    if sanitized:
                        parts.append(sanitized)
                    continue
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        sanitized = AgentFactory._strip_model_reasoning(text_value)
                        if sanitized:
                            parts.append(sanitized)
                        continue
                    nested_text = item.get("content")
                    if isinstance(nested_text, str):
                        sanitized = AgentFactory._strip_model_reasoning(nested_text)
                        if sanitized:
                            parts.append(sanitized)
            return "".join(parts)
        return ""

    @staticmethod
    def _strip_model_reasoning(content: str) -> str:
        if not content:
            return ""
        return content

    def _is_retryable_chat_error(self, exc: Exception) -> bool:
        retryable_status_codes = {408, 409, 425, 429, 500, 502, 503, 504}
        terminal_type_names = {
            "APITimeoutError",
            "ReadTimeout",
        }
        retryable_type_names = {
            "APIConnectionError",
            "RateLimitError",
            "InternalServerError",
            "RemoteProtocolError",
            "ReadError",
            "ConnectTimeout",
            "PoolTimeout",
        }
        retryable_markers = (
            "connection error",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "incomplete chunked read",
            "remoteprotocolerror",
            "peer closed connection",
            "connection reset",
            "server disconnected",
            "try again",
        )

        for current in self._iter_exception_chain(exc):
            if type(current).__name__ in terminal_type_names:
                return False

            status_code = getattr(current, "status_code", None)
            if status_code in retryable_status_codes:
                return True

            response = getattr(current, "response", None)
            response_status = getattr(response, "status_code", None)
            if response_status in retryable_status_codes:
                return True

            if type(current).__name__ in retryable_type_names:
                return True

            message = str(current).lower()
            if any(marker in message for marker in retryable_markers):
                return True

        return False

    @staticmethod
    def _iter_exception_chain(exc: Exception):
        seen = set()
        current = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            yield current
            current = current.__cause__ or current.__context__

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = (base_url or "").strip().rstrip("/")
        if not normalized:
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"

        if "api.deepseek.com" in normalized and not normalized.endswith("/v1"):
            return f"{normalized}/v1"
        return normalized

    def _resolve_system_message(self, agent) -> str:
        for attr in ("_custom_system_prompt", "system_message", "_system_message"):
            value = getattr(agent, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()

        agent_type = getattr(agent, "_agent_type", "")
        fallback_map = {
            "privacy_policy_generator": GENERATOR_FALLBACK_MESSAGE,
            "compliance_checker": COMPLIANCE_FALLBACK_MESSAGE,
            "conflict_detector": CONFLICT_FALLBACK_MESSAGE,
            "compliance_checker_multi": MULTI_COMPLIANCE_FALLBACK_MESSAGE,
            "multi_jurisdiction_coordinator": COORDINATION_FALLBACK_MESSAGE,
        }
        return fallback_map.get(agent_type, COMPLIANCE_FALLBACK_MESSAGE)

    def _build_user_message_with_files(self, message: str, uploaded_files=None) -> str:
        base_message = (message or "").strip()
        if not uploaded_files:
            return base_message

        parts = [base_message, "", "补充文件："]
        for file_info in uploaded_files:
            file_name = file_info.get("name", "uploaded_file")
            file_content = file_info.get("content", "")
            parts.append(f"[file] {file_name}")
            parts.append(file_content)
        return "\n".join(parts).strip()

    def _validate_response_by_agent_type(self, result: str, agent) -> None:
        if not result.strip():
            raise ValueError("模型返回内容为空")

        agent_type = getattr(agent, "_agent_type", "")
        keyword_map = {
            "privacy_policy_generator": ["privacy policy", "隐私政策", "data", "数据", "rights", "权利"],
            "compliance_checker": ["score", "评分", "evidence", "证据", "recommend", "建议"],
            "compliance_checker_multi": ["jurisdiction", "法域", "score", "评分", "summary", "总结"],
            "conflict_detector": ["conflict", "冲突", "severity", "严重", "remediation", "整改"],
            "multi_jurisdiction_coordinator": ["plan", "计划", "summary", "总结", "priority", "优先"],
        }
        expected = keyword_map.get(agent_type, [])
        found = [keyword for keyword in expected if keyword.lower() in result.lower()]
        if expected and not found:
            logger.warning(f"{agent_type} 的响应未包含预期标记: {expected}")

    def clear_cache(self):
        cache_size = len(self._built_agents)
        self._built_agents.clear()
        logger.info(f"Agent 缓存已清空，释放 {cache_size} 项")

    def _clean_oldest_cache(self):
        if not self._built_agents:
            return
        oldest_key = next(iter(self._built_agents))
        del self._built_agents[oldest_key]
        logger.debug(f"已移除最旧的 Agent 缓存项: {oldest_key}")

    def get_cache_info(self) -> Dict[str, Any]:
        return {
            "size": len(self._built_agents),
            "max_size": self._cache_max_size,
            "keys": list(self._built_agents.keys()),
        }

    def set_cache_max_size(self, max_size: int):
        if max_size < 1:
            raise ValueError("缓存上限必须至少为 1")
        self._cache_max_size = max_size
        while len(self._built_agents) > self._cache_max_size:
            self._clean_oldest_cache()
        logger.info(f"Agent 缓存上限已更新为 {self._cache_max_size}")
