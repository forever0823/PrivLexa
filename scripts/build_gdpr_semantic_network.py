from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ARTICLE_RE = re.compile(r"^Article (?P<number>\d+)$")
CHAPTER_RE = re.compile(r"^CHAPTER (?P<code>[IVXLCDM]+)$")
SECTION_RE = re.compile(r"^Section (?P<number>\d+)$")
PARAGRAPH_RE = re.compile(r"^(?P<number>\d+)\.\s+(?P<text>.+)$")
ITEM_RE = re.compile(r"^\((?P<code>[a-z0-9]+)\)\s+(?P<text>.+)$")

BODY_STARTERS = (
    "The ",
    "This ",
    "These ",
    "Where ",
    "For ",
    "Each ",
    "Any ",
    "Member States",
    "Natural persons",
    "Personal data",
    "Processing ",
    "Without ",
    "A ",
    "An ",
    "In ",
)

RIGHT_PATTERNS = (
    "has the right to",
    "have the right to",
    "shall have the right to",
    "right to obtain",
)

POWER_PATTERNS = (
    "shall be empowered to",
    "is empowered to",
    "may ",
)

PROHIBITION_PATTERNS = (
    "shall not",
    "may not",
)

DUTY_PATTERNS = (
    "shall ",
    "must ",
    "is required to",
    "are required to",
)

RIGHT_RE = re.compile(
    r"\b(?:has the right to|have the right to|shall have the right to|right to obtain)\b",
    re.IGNORECASE,
)
PROHIBITION_RE = re.compile(r"\b(?:shall not|may not)\b|\bprohibit(?:ed|ion)?\b|\bforbidden\b", re.IGNORECASE)
POWER_RE = re.compile(r"\b(?:shall be empowered to|is empowered to|may)\b", re.IGNORECASE)
DUTY_RE = re.compile(r"\b(?:shall|must|is required to|are required to)\b", re.IGNORECASE)

ACTOR_PATTERNS: List[Tuple[str, str]] = [
    ("data_subject", r"\bdata subject\b"),
    ("supervisory_authority", r"\bsupervisory authorit(?:y|ies)\b"),
    ("commission", r"\bcommission\b"),
    ("board", r"\bboard\b"),
    ("member_state", r"\bmember states?\b"),
    ("controller_or_processor", r"\bcontroller or processor\b"),
    ("controller_and_processor", r"\bcontroller and (the )?processor\b"),
    ("joint_controller", r"\bjoint controllers?\b"),
    ("processor", r"\bprocessor\b"),
    ("controller", r"\bcontroller\b"),
    ("representative", r"\brepresentative\b"),
    ("recipient", r"\brecipient\b"),
    ("controller_representative", r"\bcontroller'?s representative\b"),
]

SUBJECT_WITH_MODAL_RE = re.compile(
    r"\b(?P<subject>(?:the|each|a|an)\s+[^.;:]{1,120}?|member states?)\s+"
    r"(?P<modal>shall(?: not)?|must|may(?: not)?|has the right to|have the right to|"
    r"shall have the right to|is empowered to|shall be empowered to)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a GDPR semantic network with law -> clause -> obligation."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to the extracted GDPR text file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output") / "GDPR_EN_TXT.semantic_network.json",
        help="Path to the generated semantic-network JSON file.",
    )
    return parser.parse_args()


def load_lines(input_path: Path) -> List[str]:
    text = input_path.read_text(encoding="utf-8")
    lines = []
    for raw_line in text.splitlines():
        line = normalize_space(raw_line)
        if not line:
            continue
        if "Official Journal of the European Union" in line:
            continue
        lines.append(line)
    return lines


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_regulation_body(lines: List[str]) -> List[str]:
    for index, line in enumerate(lines):
        if line == "CHAPTER I":
            return lines[index:]
    raise ValueError("Could not find the start of GDPR articles at CHAPTER I.")


def split_article_content(content_lines: List[str]) -> Tuple[str, List[str]]:
    if not content_lines:
        return "", []

    title_lines = [content_lines[0]]
    body_lines: List[str] = []

    for line in content_lines[1:]:
        if body_lines:
            body_lines.append(line)
            continue
        if is_body_start(line, title_lines):
            body_lines.append(line)
        else:
            title_lines.append(line)

    return " ".join(title_lines), body_lines


def is_body_start(line: str, title_lines: List[str]) -> bool:
    if PARAGRAPH_RE.match(line) or ITEM_RE.match(line):
        return True
    if line.endswith(":"):
        return True
    if line.startswith(BODY_STARTERS):
        return True
    if len(title_lines) >= 2:
        return True
    return False


def parse_articles(lines: List[str]) -> List[Dict[str, Any]]:
    articles: List[Dict[str, Any]] = []
    current_article_number: Optional[int] = None
    current_article_lines: List[str] = []
    chapter_code: Optional[str] = None
    chapter_title: Optional[str] = None
    section_code: Optional[str] = None
    section_title: Optional[str] = None
    pending_chapter_title = False
    pending_section_title = False

    def flush_article() -> None:
        nonlocal current_article_number, current_article_lines
        if current_article_number is None:
            return
        title, body_lines = split_article_content(current_article_lines)
        articles.append(
            {
                "clause_id": f"GDPR_ART_{current_article_number}",
                "clause_type": "article",
                "law_id": "EU_GDPR_2016_679",
                "law_name": "General Data Protection Regulation",
                "jurisdiction": "EU",
                "article_number": current_article_number,
                "article_reference": f"Article {current_article_number}",
                "title": title,
                "chapter_code": chapter_code,
                "chapter_title": chapter_title,
                "section_code": section_code,
                "section_title": section_title,
                "text": format_body_text(body_lines),
                "raw_body_lines": body_lines,
            }
        )
        current_article_number = None
        current_article_lines = []

    for line in lines:
        article_match = ARTICLE_RE.match(line)
        chapter_match = CHAPTER_RE.match(line)
        section_match = SECTION_RE.match(line)

        if article_match:
            flush_article()
            current_article_number = int(article_match.group("number"))
            current_article_lines = []
            pending_chapter_title = False
            pending_section_title = False
            continue

        if chapter_match:
            flush_article()
            chapter_code = chapter_match.group("code")
            chapter_title = None
            section_code = None
            section_title = None
            pending_chapter_title = True
            pending_section_title = False
            continue

        if section_match:
            flush_article()
            section_code = section_match.group("number")
            section_title = None
            pending_section_title = True
            continue

        if pending_chapter_title:
            chapter_title = line
            pending_chapter_title = False
            continue

        if pending_section_title:
            section_title = line
            pending_section_title = False
            continue

        if current_article_number is not None:
            current_article_lines.append(line)

    flush_article()
    return articles


def format_body_text(body_lines: List[str]) -> str:
    merged: List[str] = []
    for line in body_lines:
        if PARAGRAPH_RE.match(line) or ITEM_RE.match(line):
            merged.append(line)
            continue
        if merged:
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return "\n".join(merged)


def parse_paragraphs(article: Dict[str, Any]) -> List[Dict[str, Any]]:
    body_lines: List[str] = article["raw_body_lines"]
    if not body_lines:
        return []

    paragraphs: List[Dict[str, Any]] = []
    current_number: Optional[str] = None
    current_lines: List[str] = []

    def flush_paragraph() -> None:
        nonlocal current_number, current_lines
        if not current_lines:
            return
        lead_lines: List[str] = []
        items: List[Dict[str, str]] = []
        current_item_code: Optional[str] = None
        current_item_lines: List[str] = []

        for line in current_lines:
            item_match = ITEM_RE.match(line)
            if item_match:
                if current_item_code is not None:
                    items.append(
                        {
                            "item_code": current_item_code,
                            "text": " ".join(current_item_lines),
                        }
                    )
                current_item_code = item_match.group("code")
                current_item_lines = [item_match.group("text")]
                continue

            if current_item_code is not None:
                current_item_lines.append(line)
            else:
                lead_lines.append(line)

        if current_item_code is not None:
            items.append(
                {
                    "item_code": current_item_code,
                    "text": " ".join(current_item_lines),
                }
            )

        paragraphs.append(
            {
                "paragraph_number": current_number,
                "lead_text": " ".join(lead_lines).strip(),
                "items": items,
            }
        )
        current_number = None
        current_lines = []

    for line in body_lines:
        paragraph_match = PARAGRAPH_RE.match(line)
        if paragraph_match:
            flush_paragraph()
            current_number = paragraph_match.group("number")
            current_lines = [paragraph_match.group("text")]
            continue
        current_lines.append(line)

    flush_paragraph()
    return paragraphs


def split_sentences(text: str) -> List[str]:
    normalized = normalize_space(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z])", normalized)
    return [part.strip() for part in parts if part.strip()]


def is_normative(text: str) -> bool:
    lower = text.lower()
    if lower.startswith("for the purposes of this regulation"):
        return False
    if RIGHT_RE.search(text):
        return True
    if PROHIBITION_RE.search(text):
        return True
    if DUTY_RE.search(text):
        return True
    if POWER_RE.search(text):
        return True
    return False


def classify_obligation(statement: str) -> str:
    lower = statement.lower()
    if RIGHT_RE.search(statement):
        return "right"
    if PROHIBITION_RE.search(statement):
        return "prohibition"
    if " prohibited" in lower or " forbidden" in lower:
        return "prohibition"
    if POWER_RE.search(statement) and not DUTY_RE.search(statement):
        return "power"
    return "duty"


def detect_actor(statement: str) -> str:
    subject_match = SUBJECT_WITH_MODAL_RE.search(statement)
    if subject_match:
        subject = subject_match.group("subject").lower()
        actor = map_subject_to_actor(subject)
        if actor:
            return actor

    lowered = statement.lower()
    for actor, pattern in ACTOR_PATTERNS:
        if re.search(pattern, lowered):
            return actor
    return "general"


def map_subject_to_actor(subject: str) -> Optional[str]:
    subject = subject.strip().lower()
    if "," in subject:
        subject = subject.rsplit(",", 1)[-1].strip()

    if "data subject" in subject:
        return "data_subject"
    if "supervisory authorit" in subject:
        return "supervisory_authority"
    if "controller and" in subject and "processor" in subject:
        return "controller_and_processor"
    if "controller or" in subject and "processor" in subject:
        return "controller_or_processor"
    if "joint controller" in subject:
        return "joint_controller"
    if "member state" in subject:
        return "member_state"
    if "commission" in subject:
        return "commission"
    if "board" in subject:
        return "board"
    if "processor" in subject and "controller" not in subject:
        return "processor"
    if "controller" in subject:
        return "controller"
    if "representative" in subject:
        return "representative"
    if "recipient" in subject:
        return "recipient"
    return None


def build_obligations(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    obligations: List[Dict[str, Any]] = []

    for article in articles:
        obligation_index = 1
        article["paragraphs"] = parse_paragraphs(article)
        article["obligation_ids"] = []

        for paragraph in article["paragraphs"]:
            lead_text = paragraph["lead_text"]
            paragraph_number = paragraph["paragraph_number"]
            items = paragraph["items"]

            if items and is_normative(lead_text):
                lead_prefix = lead_text.rstrip(":;")
                for item in items:
                    combined_statement = normalize_space(f"{lead_prefix} {item['text']}")
                    reference = build_reference(article["article_number"], paragraph_number, item["item_code"])
                    for statement in split_sentences(combined_statement):
                        if not is_normative(statement):
                            continue
                        obligation = build_obligation_record(
                            article=article,
                            obligation_index=obligation_index,
                            reference=reference,
                            statement=statement,
                        )
                        obligations.append(obligation)
                        article["obligation_ids"].append(obligation["obligation_id"])
                        obligation_index += 1
                continue

            for statement in split_sentences(lead_text):
                if not is_normative(statement):
                    continue
                reference = build_reference(article["article_number"], paragraph_number, None)
                obligation = build_obligation_record(
                    article=article,
                    obligation_index=obligation_index,
                    reference=reference,
                    statement=statement,
                )
                obligations.append(obligation)
                article["obligation_ids"].append(obligation["obligation_id"])
                obligation_index += 1

            if not items:
                continue

            for item in items:
                reference = build_reference(
                    article["article_number"], paragraph_number, item["item_code"]
                )
                for statement in split_sentences(item["text"]):
                    if not is_normative(statement):
                        continue
                    obligation = build_obligation_record(
                        article=article,
                        obligation_index=obligation_index,
                        reference=reference,
                        statement=statement,
                    )
                    obligations.append(obligation)
                    article["obligation_ids"].append(obligation["obligation_id"])
                    obligation_index += 1

    return obligations


def build_reference(
    article_number: int, paragraph_number: Optional[str], item_code: Optional[str]
) -> str:
    reference = f"Article {article_number}"
    if paragraph_number:
        reference += f"({paragraph_number})"
    if item_code:
        reference += f"({item_code})"
    return reference


def build_obligation_record(
    article: Dict[str, Any],
    obligation_index: int,
    reference: str,
    statement: str,
) -> Dict[str, Any]:
    return {
        "obligation_id": f"{article['clause_id']}_OBL_{obligation_index}",
        "law_id": article["law_id"],
        "clause_id": article["clause_id"],
        "jurisdiction": article["jurisdiction"],
        "article_reference": article["article_reference"],
        "source_reference": reference,
        "type": classify_obligation(statement),
        "actor": detect_actor(statement),
        "statement": statement,
    }


def build_law_record(input_path: Path, clause_count: int, obligation_count: int) -> Dict[str, Any]:
    return {
        "law_id": "EU_GDPR_2016_679",
        "code": "GDPR",
        "name": "General Data Protection Regulation",
        "official_title": (
            "Regulation (EU) 2016/679 on the protection of natural persons "
            "with regard to the processing of personal data and on the free movement of such data"
        ),
        "jurisdiction": "EU",
        "model": "law -> clause -> obligation",
        "source_file": str(input_path),
        "clause_count": clause_count,
        "obligation_count": obligation_count,
    }


def build_relations(law_id: str, clauses: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    relations: List[Dict[str, str]] = []
    for clause in clauses:
        relations.append(
            {
                "source": law_id,
                "target": clause["clause_id"],
                "relation": "contains_clause",
            }
        )
        for obligation_id in clause.get("obligation_ids", []):
            relations.append(
                {
                    "source": clause["clause_id"],
                    "target": obligation_id,
                    "relation": "imposes_obligation",
                }
            )
    return relations


def add_summary(
    law: Dict[str, Any], clauses: List[Dict[str, Any]], obligations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    type_counts = Counter(item["type"] for item in obligations)
    actor_counts = Counter(item["actor"] for item in obligations)
    chapter_counts = Counter(
        f"{clause['chapter_code']} {clause['chapter_title']}"
        for clause in clauses
        if clause.get("chapter_code") and clause.get("chapter_title")
    )
    return {
        "law_id": law["law_id"],
        "chapter_count": len(chapter_counts),
        "clauses_per_chapter": dict(chapter_counts),
        "obligations_by_type": dict(type_counts),
        "obligations_by_actor": dict(actor_counts.most_common(12)),
    }


def build_semantic_network(input_path: Path) -> Dict[str, Any]:
    lines = load_lines(input_path)
    regulation_body = extract_regulation_body(lines)
    clauses = parse_articles(regulation_body)
    obligations = build_obligations(clauses)

    clause_payload = [
        {
            key: value
            for key, value in clause.items()
            if key != "raw_body_lines"
        }
        for clause in clauses
    ]
    law = build_law_record(
        input_path=input_path,
        clause_count=len(clause_payload),
        obligation_count=len(obligations),
    )
    summary = add_summary(law=law, clauses=clause_payload, obligations=obligations)
    relations = build_relations(law_id=law["law_id"], clauses=clause_payload)

    return {
        "law": law,
        "clauses": clause_payload,
        "obligations": obligations,
        "relations": relations,
        "summary": summary,
    }


def main() -> int:
    args = parse_args()
    semantic_network = build_semantic_network(args.input_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(semantic_network, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Built semantic network: {args.output} "
        f"(clauses={semantic_network['law']['clause_count']}, "
        f"obligations={semantic_network['law']['obligation_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
