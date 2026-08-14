"""
Readability checker builder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent
from loguru import logger

try:
    from prompt.readability_checker_prompt import DESCRIPTION, SYSTEM_PROMPT
except ImportError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from prompt.readability_checker_prompt import DESCRIPTION, SYSTEM_PROMPT

try:
    from src.core.memory.list_memory import ListMemoryManager
except ImportError:
    from ..core.memory.list_memory import ListMemoryManager

try:
    from src.utils.utils import get_memory_dir
except ImportError:
    from ..utils.utils import get_memory_dir


class ReadabilityCheckerBuilder:
    def __init__(self, model_client, tools=None, memory_files=None):
        self.model_client = model_client
        self.tools = tools or []
        self.memory_files = memory_files or []

    async def build(self):
        memories = []
        for name in self.memory_files:
            manager = ListMemoryManager(os.path.join(get_memory_dir(), name))
            memories.append(await manager.get_memory())

        agent = AssistantAgent(
            name="readability_checker_agent",
            model_client=self.model_client,
            description=DESCRIPTION,
            system_message=SYSTEM_PROMPT,
            tools=self.tools,
            memory=memories,
            model_client_stream=True,
        )
        agent._agent_type = "readability_checker"
        agent._custom_system_prompt = SYSTEM_PROMPT
        if not getattr(agent, "system_message", None):
            agent.system_message = SYSTEM_PROMPT
            agent._system_message = SYSTEM_PROMPT
        logger.info("可读性检测 Agent 构建完成")
        return agent
