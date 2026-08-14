"""防止用户可见提示词回退为中英混合版本。"""

from pathlib import Path

from prompt.compliance_checker_prompt import SYSTEM_PROMPT as COMPLIANCE_PROMPT
from prompt.privacy_policy_generator_prompt import SYSTEM_PROMPT as GENERATOR_PROMPT
from prompt.readability_checker_prompt import SYSTEM_PROMPT as READABILITY_PROMPT


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_RUNTIME_FILES = [
    PROJECT_ROOT / "prompt" / "privacy_policy_generator_prompt.py",
    PROJECT_ROOT / "prompt" / "compliance_checker_prompt.py",
    PROJECT_ROOT / "prompt" / "readability_checker_prompt.py",
    PROJECT_ROOT / "src" / "agents" / "agent_factory.py",
    PROJECT_ROOT / "src" / "agents" / "privacy_policy_generator_builder.py",
    PROJECT_ROOT / "src" / "agents" / "readability_checker_builder.py",
    PROJECT_ROOT / "src" / "agents" / "conflict_detector_builder.py",
    PROJECT_ROOT / "src" / "agents" / "multi_jurisdiction_coordinator_builder.py",
    PROJECT_ROOT / "src" / "agents" / "compliance_checker_builder.py",
    PROJECT_ROOT / "src" / "agents" / "compliance_checker_builder_multi_jurisdiction.py",
    PROJECT_ROOT / "src" / "api" / "routes.py",
    PROJECT_ROOT / "src" / "core" / "compliance_runtime.py",
    PROJECT_ROOT / "src" / "core" / "jurisdiction.py",
]


def test_primary_prompts_explicitly_require_simplified_chinese() -> None:
    for prompt in (GENERATOR_PROMPT, COMPLIANCE_PROMPT, READABILITY_PROMPT):
        assert "简体中文" in prompt


def test_runtime_prompts_do_not_restore_legacy_english_directives() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in PROMPT_RUNTIME_FILES)
    forbidden_fragments = (
        "You are ",
        "## Output Requirements",
        "Target jurisdiction:",
        "Generate a privacy policy for",
        "Check the following privacy policy",
        "Run the following multi-jurisdiction",
        "[TO_BE_CONFIRMED:",
    )
    for fragment in forbidden_fragments:
        assert fragment not in source
