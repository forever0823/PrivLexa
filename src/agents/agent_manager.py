"""
Agent 管理器：负责选择 Agent 并转发请求。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

from .agent_factory import AgentFactory


class AgentManager:
    def __init__(self):
        self.factory = AgentFactory()
        self.agents: Dict[str, Any] = {}

    async def get_available_agents(self) -> List[Dict[str, Any]]:
        return await self.factory.get_available_agents()

    def _get_or_create_loop(self):
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            # 同步入口调用异步 Agent 构建时，确保当前线程总有可用事件循环。
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def get_agent(self, agent_type: str):
        if agent_type not in self.agents:
            loop = self._get_or_create_loop()
            self.agents[agent_type] = loop.run_until_complete(self.factory.build_agent(agent_type))
        return self.agents[agent_type]

    def get_agent_status(self) -> Dict[str, Any]:
        loop = self._get_or_create_loop()
        agents = loop.run_until_complete(self.get_available_agents())
        return {
            "total_agents": len(agents),
            "active_agents": len(self.agents),
            "agents": {agent["type"]: {"status": agent["status"]} for agent in agents},
        }

    def select_agent_by_intent(self, message: str) -> str:
        source_text = message or ""
        normalized = source_text.lower()

        if any(keyword in normalized for keyword in ["generate", "create", "draft"]) or any(
            keyword in source_text for keyword in ["\u751f\u6210", "\u521b\u5efa", "\u5199\u4e00\u4e2a"]
        ):
            return "privacy_policy_generator"
        if any(keyword in normalized for keyword in ["compliance", "review", "audit"]) or any(
            keyword in source_text for keyword in ["\u5408\u89c4", "\u68c0\u67e5", "\u7b26\u5408\u6cd5\u89c4"]
        ):
            return "compliance_checker"
        return "privacy_policy_generator"

    async def process_request(
        self,
        agent_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            tools = context.get("tools", []) if context else []
            memory_files = context.get("memory_files", []) if context else []
            result = await self.factory.chat_with_agent(
                agent_type=agent_type,
                message=message,
                tools=tools,
                memory_files=memory_files,
            )
            return {
                "success": True,
                "agent_type": agent_type,
                "response": result.get("response"),
                "message": "请求处理完成",
            }
        except Exception as exc:
            logger.error(f"处理请求失败: {exc}")
            return {
                "success": False,
                "agent_type": agent_type,
                "message": "请求处理失败",
                "error": str(exc),
            }

    async def auto_process_request(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        selected_agent = self.select_agent_by_intent(message)
        result = await self.process_request(
            agent_type=selected_agent,
            message=message,
            context=context,
        )
        result["selected_agent"] = selected_agent
        return result
