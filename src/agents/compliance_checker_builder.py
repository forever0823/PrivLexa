"""
Single-jurisdiction compliance checker builder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent
from loguru import logger

try:
    from prompt.compliance_checker_prompt import DESCRIPTION, SYSTEM_PROMPT
except ImportError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from prompt.compliance_checker_prompt import DESCRIPTION, SYSTEM_PROMPT

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

try:
    from src.core.skill_loader import (
        JURISDICTION_COMPLIANCE_SKILLS,
        load_jurisdiction_compliance_skill,
    )
except ImportError:
    from ..core.skill_loader import (
        JURISDICTION_COMPLIANCE_SKILLS,
        load_jurisdiction_compliance_skill,
    )

class ComplianceCheckerBuilder:
    def __init__(self, model_client, tools=None, memory_files=None, jurisdiction="CN"):
        self.model_client = model_client
        self.tools = tools or []
        self.memory_files = memory_files or []
        self.jurisdiction = jurisdiction
        self.jurisdiction_manager = get_jurisdiction_manager()

    async def build(self):
        memories = []
        for name in self.memory_files:
            manager = ListMemoryManager(os.path.join(get_memory_dir(), name))
            memories.append(await manager.get_memory())

        system_prompt = self._build_system_prompt()
        agent = AssistantAgent(
            name="compliance_checker_agent",
            model_client=self.model_client,
            description=DESCRIPTION,
            system_message=system_prompt,
            tools=self.tools,
            memory=memories,
            model_client_stream=True,
        )
        agent._agent_type = "compliance_checker"
        agent._jurisdiction = self.jurisdiction
        agent._enabled_skills = self._resolve_enabled_skills()
        agent._custom_system_prompt = system_prompt
        if not getattr(agent, "system_message", None):
            agent.system_message = system_prompt
            agent._system_message = system_prompt
        logger.info(f"合规检测 Agent 构建完成: jurisdiction={self.jurisdiction}")
        return agent

    def _resolve_enabled_skills(self):
        config = self.jurisdiction_manager.get_jurisdiction(self.jurisdiction)
        if not config:
            return []
        mapping = JURISDICTION_COMPLIANCE_SKILLS.get(config.code)
        return [mapping[0]] if mapping else []

    def _build_system_prompt(self) -> str:
        config = self.jurisdiction_manager.get_jurisdiction(self.jurisdiction)
        if not config:
            config = self.jurisdiction_manager.get_jurisdiction("CN")

        lines = [
            SYSTEM_PROMPT.strip(),
            "",
            "## 当前审查范围",
            f"- 法域: {config.name} ({config.code})",
            f"- 适用法律: {', '.join(config.laws)}",
            f"- 法域描述: {config.description}",
            f"- 重点义务标识: {', '.join(config.required_obligation_ids[:8])}",
            "",
            "## 法域特定审查指令",
            f"- {config.compliance_prompt}",
            "- 以所选法域作为主要法律基线。",
            "- 如果法域为欧盟，严格适用面向 GDPR 的分类体系和概念缺失检测方法。",
            "- 如果法域非欧盟，保持相同的证据驱动和逐条标准工作流，但将发现映射到所选法域的义务体系。",
            "",
            "## 重点检查项",
        ]
        lines.extend(f"- {item}" for item in config.compliance_points[:10])
        lines.extend(
            [
                "",
                "## 输出约束",
                "- 在标题、段落和条款层面进行审查，而非仅在文档层面。",
                "- 引用政策证据或明确说明缺少证据。",
                "- 全文使用统一的中文状态标签：已覆盖 / 部分覆盖 / 缺失 / 冲突 / 高风险 / 待确认。",
                "- 区分缺失披露、不充分披露、冲突披露、高风险缺陷和待确认事实。",
                "- 将每个差距映射到相关法律义务。",
                "- 最后给出优先整改行动列表。",
                "",
                "## 输出规则",
                "- 使用统一的中文标签提供合规评分和状态。",
                "- 使用逐条标准审查风格，便于下游系统解析。",
                "- 当适用性不确定时，说明触发条件和需确认的事实。",
            ]
        )
        if config.code in JURISDICTION_COMPLIANCE_SKILLS:
            skill_name = JURISDICTION_COMPLIANCE_SKILLS[config.code][0]
            skill = load_jurisdiction_compliance_skill(config.code)
            if skill:
                lines.extend(
                    [
                        "",
                        "## 已激活本地技能",
                        f"- 已选择 {config.code} 法域。将本地 {skill_name} 技能作为本次审查的主导工作流。",
                        "- 如果通用审查指令与已激活技能冲突，以已激活技能为准。",
                        "",
                        skill.to_prompt_context(),
                    ]
                )
            else:
                lines.extend(
                    [
                        "",
                        "## 技能回退",
                        f"- 已选择 {config.code} 法域，但本地 {skill_name} 技能未找到。",
                        "- 使用内置法域审查工作流作为替代。",
                    ]
                )
        lines.extend(
            [
                "",
                "## 状态标签标准化",
                "- 保持已激活技能的工作流、分类体系和证据规则。",
                "- 将所有内部或遗留状态统一为：已覆盖、部分覆盖、缺失、冲突、高风险、待确认。",
                "- 最终报告不得输出英文状态标签。",
            ]
        )
        return "\n".join(lines)
