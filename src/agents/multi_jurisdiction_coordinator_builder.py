"""多法域任务协调智能体构建器。"""

from __future__ import annotations

import os

from autogen_agentchat.agents import AssistantAgent
from loguru import logger

try:
    from src.core.memory.list_memory import ListMemoryManager
except ImportError:
    from ..core.memory.list_memory import ListMemoryManager

try:
    from src.utils.utils import get_memory_dir
except ImportError:
    from ..utils.utils import get_memory_dir

try:
    from src.core.jurisdiction import get_jurisdiction_manager
except ImportError:
    from ..core.jurisdiction import get_jurisdiction_manager


class MultiJurisdictionCoordinatorBuilder:
    def __init__(self, model_client, tools=None, memory_files=None, operation="full", parallel_processing=True):
        self.model_client = model_client
        self.tools = tools or []
        self.memory_files = memory_files or []
        self.operation = operation
        self.parallel_processing = parallel_processing
        self.jurisdiction_manager = get_jurisdiction_manager()

    async def build(self):
        memories = []
        for name in self.memory_files:
            manager = ListMemoryManager(os.path.join(get_memory_dir(), name))
            memories.append(await manager.get_memory())

        system_prompt = self._build_system_prompt()
        agent = AssistantAgent(
            name="multi_jurisdiction_coordinator_agent",
            model_client=self.model_client,
            description="协调多法域隐私政策生成、冲突检测和合规审查。",
            system_message=system_prompt,
            tools=self.tools,
            memory=memories,
            model_client_stream=True,
        )
        agent._agent_type = "multi_jurisdiction_coordinator"
        agent._operation = self.operation
        agent._parallel_processing = self.parallel_processing
        agent._custom_system_prompt = system_prompt
        if not getattr(agent, "system_message", None):
            agent.system_message = system_prompt
            agent._system_message = system_prompt
        logger.info(
            f"多法域协调 Agent 构建完成: operation={self.operation}, parallel={self.parallel_processing}"
        )
        return agent

    def _build_system_prompt(self) -> str:
        jurisdictions = self.jurisdiction_manager.list_jurisdictions()
        lines = [
            "你是多法域隐私政策任务协调智能体。",
            "基于法规知识图谱协调政策生成、混合冲突检测和并行合规审查。",
            "除非用户明确指定其他语言，全文使用简体中文。",
            "",
            "## 支持的法域",
        ]
        for item in jurisdictions:
            lines.append(f"- {item['name']} ({item['code']}): {item['description']}")
        lines.extend(
            [
                "",
                "## 协调规则",
                "- 保持中国、美国加州和欧盟之间的严格共同基线。",
                "- 规则存在冲突时，先说明冲突，再提出协调方案。",
                f"- 当前操作：{self.operation}",
                f"- 并行处理：{'启用' if self.parallel_processing else '关闭'}",
                "",
                "## 输出规则",
                "- 先给出执行计划。",
                "- 分别总结生成、冲突检测和合规审查结果。",
                "- 最后给出按优先级排序的整改清单。",
            ]
        )
        return "\n".join(lines)
