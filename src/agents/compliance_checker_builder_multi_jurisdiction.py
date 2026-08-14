"""
Multi-jurisdiction compliance checker builder.
"""

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


DESCRIPTION = "并行审查中国、美国加州和欧盟的隐私政策合规情况，并输出协调后的综合评估。"


class ComplianceCheckerBuilder:
    def __init__(
        self,
        model_client,
        tools=None,
        memory_files=None,
        jurisdictions=None,
        parallel_execution=True,
        return_markdown=False,
    ):
        self.model_client = model_client
        self.tools = tools or []
        self.memory_files = memory_files or []
        self.jurisdictions = jurisdictions or ["CN"]
        self.parallel_execution = parallel_execution
        self.return_markdown = return_markdown
        self.jurisdiction_manager = get_jurisdiction_manager()

    async def build(self):
        memories = []
        for name in self.memory_files:
            manager = ListMemoryManager(os.path.join(get_memory_dir(), name))
            memories.append(await manager.get_memory())

        system_prompt = self._build_system_prompt()
        agent = AssistantAgent(
            name="compliance_checker_multi_agent",
            model_client=self.model_client,
            description=DESCRIPTION,
            system_message=system_prompt,
            tools=self.tools,
            memory=memories,
            model_client_stream=True,
        )
        agent._agent_type = "compliance_checker_multi"
        agent._jurisdictions = self.jurisdictions
        agent._parallel_execution = self.parallel_execution
        agent._return_markdown = self.return_markdown
        agent._enabled_skills = self._resolve_enabled_skills()
        agent._custom_system_prompt = system_prompt
        if not getattr(agent, "system_message", None):
            agent.system_message = system_prompt
            agent._system_message = system_prompt
        logger.info(
            f"多法域合规检测 Agent 构建完成: jurisdictions={self.jurisdictions}, parallel={self.parallel_execution}"
        )
        return agent

    def _resolve_enabled_skills(self):
        normalized = self.jurisdiction_manager.sanitize_jurisdictions(self.jurisdictions)
        enabled = []
        for code in normalized:
            mapping = JURISDICTION_COMPLIANCE_SKILLS.get(code)
            if mapping:
                enabled.append(mapping[0])
        return enabled

    def _build_system_prompt(self) -> str:
        normalized = self.jurisdiction_manager.sanitize_jurisdictions(self.jurisdictions)
        lines = [
            "你是一位资深的多法域隐私合规审查专家。",
            "你的任务是对一份隐私政策进行并行审查，覆盖中国、美国加州和欧盟三大法域。",
            "你必须产出一份专业、深入、可执行的合规审查报告。",
            "",
            "**语言要求：全文必须使用简体中文输出，不得中英文混杂。**",
            "- 法律名称首次出现时采用“中文全称（通用缩写）”，后续可使用缩写。",
            "- 法条引用使用中文格式，例如“《中华人民共和国个人信息保护法》第 28 条”。",
            "- 法域名称用中文：中国、美国（加州）、欧盟。",
            "- 术语用中文：敏感个人信息、数据控制者、数据处理者、标准合同条款、跨境传输。",
            "- 如果政策原文是英文，用中文翻译后引用关键内容。",
            "",
            "---",
            "",
            "# 输出结构要求（严格遵循以下 Markdown 结构）",
            "",
            "## 1. 概述",
            "- 审查政策名称",
            "- 审查时间",
            "- 审查模式：并行审查",
            "- 总体状态（合规 / 部分合规 / 高风险）",
            "- 总体评分（0-100 分制，综合三法域加权）",
            "",
            "## 2. 分法域审查结果",
            "对每个法域分别输出以下子章节：",
            "",
            "### [法域名] (代码)",
            "- **状态**：已覆盖 / 部分覆盖 / 缺失 / 高风险",
            "- **评分**：X/100",
            "- **证据**：",
            "  - **优势**：逐条列出政策中做得好的地方，引用具体条款或段落。",
            "  - **不足**：逐条列出不足之处，说明问题所在。",
            "- **合规差距**：编号列表，每条差距必须：",
            "  1. 指出具体缺失或不合规的内容",
            "  2. 引用对应的法律条文，例如《中华人民共和国个人信息保护法》第 28—30 条、《通用数据保护条例》第 46 条",
            "  3. 说明对用户权益的影响",
            "- **补救措施**：编号列表，每条措施必须具体、可操作、可验证。",
            "",
            "## 3. 跨法域总结与优先级行动清单",
            "- **严格共同基线识别**：列出所有法域的共同合规要求。",
            "- **关键跨法域差距**：识别跨越多个法域的系统性问题。",
            "- **优先级行动清单**：以表格形式呈现，包含列：优先级 (P1/P2/P3)、行动项、涉及法域、说明。",
            "",
            "## 4. 冲突检测结果",
            "如果提供了冲突检测基线数据，在此章节分析条款冲突。",
            "包括：统计概览、硬冲突详情、软冲突详情、修复建议。",
            "",
            "---",
            "",
            "# 审查方法论",
            "",
            "## 法律知识基线",
        ]
        for code in normalized:
            config = self.jurisdiction_manager.get_jurisdiction(code)
            if not config:
                continue
            lines.append(f"- **{config.name} ({config.code})**：{', '.join(config.laws)}")
            lines.append(f"  重点义务: {', '.join(config.compliance_points[:8])}")
        lines.extend(
            [
                "",
                "## 审查工作流",
                "1. **条款映射**：将政策文本映射到各法域的合规主题。",
                "2. **逐项审查**：对每个主题检查：数据类别、处理目的、法律依据、接收方、保留期限、权利行使路径、跨境传输、敏感数据、未成年人保护。",
                "3. **差距分析**：将政策内容与法律要求逐一对比，识别缺失、不足或冲突。",
                "4. **评分**：基于覆盖度和质量给出 0-100 分。",
                "5. **跨法域综合**：识别共同基线和法域特定要求。",
                "",
                "## 确定性基线数据的使用",
                "用户消息中会包含「确定性基线分析」数据（基于关键词匹配和知识图谱检索）。",
                "这些数据是辅助参考，帮助你识别政策中已覆盖和未覆盖的义务主题。",
                "你的分析应以你的深度法律判断为主，基线数据为辅。",
                "如果基线数据中某个主题被标记为「已覆盖」但你的分析认为覆盖不充分，以你的判断为准。",
                "",
                "## 评分标准",
                "- 90-100: 全面合规，仅有微小改进空间",
                "- 75-89: 基本合规，存在中等改进需求",
                "- 60-74: 部分合规，存在重大改进空间",
                "- 40-59: 合规不足，存在高风险差距",
                "- 0-39: 严重不合规，需立即整改",
                "",
                "---",
                "",
                "# 语言与格式要求",
                "- 全文使用中文输出。",
                "- 法律条文引用使用中文格式（如「PIPL 第 28 条」而非「PIPL Article 28」）。",
                "- 使用 Markdown 格式化，合理使用标题层级、粗体、列表、表格。",
                "- 保持专业、客观、证据驱动的语气。",
                "- 不要使用 emoji。",
            ]
        )
        enabled_skills = self._resolve_enabled_skills()
        if enabled_skills:
            lines.extend(
                [
                    "",
                    "## 法域特定技能",
                    "- 对以下法域使用本地合规技能作为审查工作流的补充参考。",
                    "- 保持多法域综合视角，不要被单一法域技能局限。",
                ]
            )
            for code in normalized:
                mapping = JURISDICTION_COMPLIANCE_SKILLS.get(code)
                if not mapping:
                    continue
                skill_name = mapping[0]
                skill = load_jurisdiction_compliance_skill(code)
                if skill:
                    lines.extend(
                        [
                            "",
                            f"### {code} 技能分支",
                            f"- 对 {code} 审查分支应用本地 {skill_name} 技能。",
                            skill.to_prompt_context(),
                        ]
                    )
                else:
                    lines.extend(
                        [
                            "",
                            f"### {code} 技能回退",
                            f"- {code} 已包含，但本地 {skill_name} 技能未找到。",
                            "- 使用内置审查工作流作为替代。",
                        ]
                    )
        lines.extend(
            [
                "",
                "## 状态标签标准化",
                "- 所有最终状态统一为：已覆盖、部分覆盖、缺失、冲突、高风险、待确认。",
                "- 最终报告不得输出英文状态标签。",
            ]
        )
        return "\n".join(lines)
