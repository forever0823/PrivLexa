"""采用混合检测策略的条款冲突检测智能体构建器。"""

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


class ConflictDetectorBuilder:
    def __init__(self, model_client, tools=None, memory_files=None, detection_mode="both"):
        self.model_client = model_client
        self.tools = tools or []
        self.memory_files = memory_files or []
        self.detection_mode = detection_mode

    async def build(self):
        memories = []
        for name in self.memory_files:
            manager = ListMemoryManager(os.path.join(get_memory_dir(), name))
            memories.append(await manager.get_memory())

        system_prompt = self._build_system_prompt()
        agent = AssistantAgent(
            name="conflict_detector_agent",
            model_client=self.model_client,
            description="结合规则推理和语义相似度识别隐私政策中的条款冲突。",
            system_message=system_prompt,
            tools=self.tools,
            memory=memories,
            model_client_stream=True,
        )
        agent._agent_type = "conflict_detector"
        agent._detection_mode = self.detection_mode
        agent._custom_system_prompt = system_prompt
        if not getattr(agent, "system_message", None):
            agent.system_message = system_prompt
            agent._system_message = system_prompt
        logger.info(f"冲突检测 Agent 构建完成: mode={self.detection_mode}")
        return agent

    def _build_system_prompt(self) -> str:
        mode_map = {
            "hard": "仅输出基于规则推理发现的硬冲突。",
            "soft": "仅输出基于语义相似度分析发现的软冲突。",
            "both": "同时输出硬冲突和软冲突，并提供合并结论。",
        }
        lines = [
            "你是一位隐私政策条款冲突检测专家。",
            "使用混合工作流：规则推理检测硬冲突，语义相似度分析检测软冲突。",
            "",
            "## 主要检测主题",
            "- 保存期限",
            "- 同意要求",
            "- 第三方共享与出售",
            "- 用户权利",
            "- 跨境传输",
            "",
            "## 当前模式",
            f"- {mode_map.get(self.detection_mode, mode_map['both'])}",
            "",
            "## 输出结构要求",
            "",
            "### 统计概览",
            "- 总冲突数、硬冲突数、软冲突数、冲突率评估",
            "",
            "### 冲突详情",
            "对每个冲突输出：",
            "- 严重程度（高/中/低）",
            "- 冲突类型（硬冲突/软冲突）",
            "- 涉及条款：引用具体条款位置和内容",
            "- 冲突原因：说明逻辑矛盾或语义不一致的具体表现",
            "- 如果是软冲突，包含语义相似度分数",
            "- 修复建议：具体、可操作的修改方案",
            "",
            "### 合并结论与总体评估",
            "- 政策一致性总体评价",
            "- 改进建议优先级（高/中/低）",
            "- 风险等级评估",
            "",
            "## 语言与格式要求",
            "- 全文使用中文输出。",
            "- 使用 Markdown 格式化。",
            "- 保持专业、客观的语气。",
            "- 如果提供了结构化预分析数据，将其作为基线证据使用，而非忽略。",
        ]
        return "\n".join(lines)
