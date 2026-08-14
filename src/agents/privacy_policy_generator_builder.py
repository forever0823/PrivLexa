"""面向多法域架构的隐私政策生成智能体构建器。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent
from loguru import logger

try:
    from prompt.privacy_policy_generator_prompt import DESCRIPTION, SYSTEM_PROMPT
except ImportError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from prompt.privacy_policy_generator_prompt import DESCRIPTION, SYSTEM_PROMPT

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

class PrivacyPolicyGeneratorBuilder:
    def __init__(self, model_client, tools=None, memory_files=None, jurisdiction=None, use_rag=False):
        self.model_client = model_client
        self.tools = tools or []
        self.memory_files = memory_files or []
        self.jurisdiction = jurisdiction or "CN"
        self.use_rag = use_rag
        self.jurisdiction_manager = get_jurisdiction_manager()

    async def build(self):
        memories = []
        for name in self.memory_files:
            manager = ListMemoryManager(os.path.join(get_memory_dir(), name))
            memories.append(await manager.get_memory())

        system_prompt = self._build_system_prompt()
        agent = AssistantAgent(
            name="privacy_policy_generator_agent",
            model_client=self.model_client,
            description=DESCRIPTION,
            system_message=system_prompt,
            tools=self.tools,
            memory=memories,
            model_client_stream=True,
        )
        agent._agent_type = "privacy_policy_generator"
        agent._jurisdiction = self.jurisdiction
        agent._use_rag = self.use_rag
        agent._custom_system_prompt = system_prompt
        if not getattr(agent, "system_message", None):
            agent.system_message = system_prompt
            agent._system_message = system_prompt
        logger.info(
            f"隐私政策生成 Agent 构建完成: jurisdiction={self.jurisdiction}, use_rag={self.use_rag}"
        )
        return agent

    def _build_system_prompt(self) -> str:
        config = self.jurisdiction_manager.get_jurisdiction(self.jurisdiction)
        if not config:
            config = self.jurisdiction_manager.get_jurisdiction("CN")

        lines = [
            SYSTEM_PROMPT.strip(),
            "",
            "## 目标法域画像",
            f"- 法域：{config.name}（{config.code}）",
            f"- 地区：{config.region}",
            f"- 说明：{config.description}",
            f"- 适用法律：{', '.join(config.laws)}",
            f"- 法域画像：{config.jurisdiction_embedding}",
            "",
            "## 法域特定起草指令",
            f"- {config.system_prompt}",
            "- 除非用户明确要求多法域协调版本，否则草案只适配当前目标法域。",
            "- 条款在不同法域存在差异时，仅保留目标法域规则，或明确标注差异。",
            "- 将必备义务和检索证据视为起草约束，而不是可选建议。",
            "",
            "## 必须覆盖的主题",
        ]
        lines.extend(f"- {item}" for item in config.compliance_points[:12])
        lines.extend(
            [
                "",
                "## 必备义务锚点",
                "- 在相关场景中使用以下义务标识作为起草参考：",
            ]
        )
        lines.extend(
            f"- {obligation_id}" for obligation_id in config.required_obligation_ids[:12]
        )
        lines.extend(
            [
                "",
                "## 输出要求",
                "- 生成面向普通用户的完整隐私政策。",
                "- 包含收集、使用、共享、保存、安全、用户权利、未成年人保护、联系方式和投诉渠道等可执行条款。",
                "- 信息缺失时使用“[待确认：具体事实]”，不得编造。",
                "- 保持适合后续合规审查和冲突检测的文档结构。",
                "- 除非用户明确指定其他语言，全文使用简体中文。",
            ]
        )
        if self.use_rag:
            lines.extend(
                [
                    "",
                    "## 法规检索增强要求",
                    "- 将检索到的法规条款作为必须参考的起草证据。",
                    "- 用户要求含糊时，优先采用更严格、更透明的解释。",
                ]
            )
        return "\n".join(lines)
