"""
Prompt包初始化文件
导出各个Agent的Prompt和描述
"""

from .compliance_checker_prompt import DESCRIPTION as COMPLIANCE_CHECKER_DESCRIPTION
from .compliance_checker_prompt import SYSTEM_PROMPT as COMPLIANCE_CHECKER_PROMPT
# 导出各个Agent的Prompt和描述
from .privacy_policy_generator_prompt import DESCRIPTION as PRIVACY_POLICY_GENERATOR_DESCRIPTION
from .privacy_policy_generator_prompt import SYSTEM_PROMPT as PRIVACY_POLICY_GENERATOR_PROMPT
from .readability_checker_prompt import DESCRIPTION as READABILITY_CHECKER_DESCRIPTION
from .readability_checker_prompt import SYSTEM_PROMPT as READABILITY_CHECKER_PROMPT

__all__ = [
    "PRIVACY_POLICY_GENERATOR_DESCRIPTION",
    "PRIVACY_POLICY_GENERATOR_PROMPT",
    "COMPLIANCE_CHECKER_DESCRIPTION",
    "COMPLIANCE_CHECKER_PROMPT",
    "READABILITY_CHECKER_DESCRIPTION",
    "READABILITY_CHECKER_PROMPT"
]
