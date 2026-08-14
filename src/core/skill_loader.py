"""将本地合规技能加载到后端提示词中。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import os
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from loguru import logger


@dataclass(frozen=True)
class LoadedSkill:
    name: str
    source_dir: Path
    instructions: str
    references: Dict[str, str] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        parts = [
            f"已启用本地审查技能：{self.name}",
            "技能材料中的英文仅用于法律缩写、原始术语或结构化字段标识；最终报告必须使用简体中文。",
            "",
            "技能说明：",
            self.instructions.strip(),
        ]
        for reference_name, content in self.references.items():
            parts.extend(
                [
                    "",
                    f"技能参考资料：{reference_name}",
                    content.strip(),
                ]
            )
        return "\n".join(parts).strip()


JURISDICTION_COMPLIANCE_SKILLS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "CN": (
        "cn-app-privacy-compliance-review",
        ("cn-hierarchical-method.md", "cn-evaluation-taxonomy.md"),
    ),
    "US": (
        "ccpa-app-privacy-compliance-review",
        ("ccpa-app-method.md", "ccpa-app-taxonomy.md"),
    ),
    "EU": (
        "gdpr-compliance-review",
        ("gdpr-review-reference.md",),
    ),
}


def _dedupe_paths(paths: Iterable[Path]) -> Tuple[Path, ...]:
    unique = []
    seen = set()
    for path in paths:
        normalized = str(path.resolve(strict=False)).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(path)
    return tuple(unique)


def _candidate_skill_dirs(skill_name: str) -> Tuple[Path, ...]:
    project_root = Path(__file__).resolve().parents[2]
    codex_home = os.getenv("CODEX_HOME")
    skills_dir = os.getenv("PPGLLM_SKILLS_DIR")

    candidates = []
    if skills_dir:
        candidates.append(Path(skills_dir) / skill_name)
    if codex_home:
        candidates.append(Path(codex_home) / "skills" / skill_name)
    candidates.append(Path.home() / ".codex" / "skills" / skill_name)
    candidates.append(project_root / "skills" / skill_name)
    return _dedupe_paths(candidates)


def _strip_frontmatter(text: str) -> str:
    normalized = text.lstrip()
    if not normalized.startswith("---"):
        return text.strip()

    lines = normalized.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return text.strip()

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return text.strip()


@lru_cache(maxsize=32)
def load_local_skill(skill_name: str, reference_names: Tuple[str, ...] = ()) -> Optional[LoadedSkill]:
    for skill_dir in _candidate_skill_dirs(skill_name):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            instructions = _strip_frontmatter(skill_file.read_text(encoding="utf-8"))
            references: Dict[str, str] = {}
            for reference_name in reference_names:
                reference_path = skill_dir / "references" / reference_name
                if reference_path.exists():
                    references[reference_name] = reference_path.read_text(encoding="utf-8").strip()

            loaded = LoadedSkill(
                name=skill_name,
                source_dir=skill_dir,
                instructions=instructions,
                references=references,
            )
            logger.info(f"Loaded local skill '{skill_name}' from {skill_dir}")
            return loaded
        except Exception as exc:
            logger.warning(f"Failed to load skill '{skill_name}' from {skill_dir}: {exc}")

    logger.warning(f"Local skill '{skill_name}' was not found in configured search paths")
    return None


def load_jurisdiction_compliance_skill(jurisdiction_code: str) -> Optional[LoadedSkill]:
    mapping = JURISDICTION_COMPLIANCE_SKILLS.get(jurisdiction_code)
    if not mapping:
        return None
    skill_name, reference_names = mapping
    return load_local_skill(skill_name, reference_names=reference_names)
