from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


SECTION_RE = re.compile(r"^(?P<number>1798\.\d+(?:\.\d+)?)\.\s*(?P<rest>.*)$")
LEADING_LABELS_RE = re.compile(r"^(?P<labels>(?:\([A-Za-z0-9ivxIVX]+\)\s*)+)(?P<text>.*)$")
LABEL_RE = re.compile(r"\(([A-Za-z0-9ivxIVX]+)\)")
PAGE_RE = re.compile(r"^Page \d+ of \d+$", re.IGNORECASE)

RIGHT_RE = re.compile(
    r"\b(?:shall have the right to|has the right to|have the right to|right to request|right to direct)\b",
    re.IGNORECASE,
)
EXCEPTION_RE = re.compile(
    r"\b(?:shall not apply|does not apply|not required to comply|shall not be required to comply|"
    r"shall not be required|does not require|is not obligated to|is not required to)\b",
    re.IGNORECASE,
)
PROHIBITION_RE = re.compile(
    r"\b(?:shall not|may not|prohibits?|precluded|refrain from)\b",
    re.IGNORECASE,
)
POWER_RE = re.compile(
    r"\b(?:may|is authorized to|are authorized to|shall be empowered to|is empowered to)\b",
    re.IGNORECASE,
)
DUTY_RE = re.compile(
    r"\b(?:shall|must|is required to|are required to|obligates?|requires?)\b",
    re.IGNORECASE,
)
IMPERATIVE_RE = re.compile(
    r"^(?:Ensure|Provide|Include|Use|Display|Permit|Grant|Require|Notify|Disclose|Make|Honor|"
    r"Allow|Delete|Correct|Cooperate|Maintain|Complete|Help|Debug|Exercise|Comply|Engage|"
    r"Take|Protect|Stop|Remediate|Specify|Issue|Update|Review|Promote|Solicit|Monitor|Administer|"
    r"Clearly|State)\b",
    re.IGNORECASE,
)

BODY_STARTERS = (
    "A ",
    "An ",
    "Any ",
    "No ",
    "The ",
    "This title",
    "Subject to",
    "On or before",
    "Beginning ",
    "There is",
    "If ",
    "In ",
    "Notwithstanding",
    "Whenever ",
    "Funds ",
    "Members ",
)

ACTOR_PATTERNS: List[Tuple[str, str]] = [
    ("regulated_entity", r"\bbusiness, service provider, contractor, or other person\b"),
    ("california_privacy_protection_agency", r"\bcalifornia privacy protection agency\b|\bthe agency\b"),
    ("attorney_general", r"\battorney general\b"),
    ("consumer", r"\bconsumer\b"),
    ("business", r"\bbusiness\b"),
    ("service_provider", r"\bservice provider\b"),
    ("contractor", r"\bcontractor\b"),
    ("third_party", r"\bthird part(?:y|ies)\b"),
    ("court", r"\bcourt\b"),
    ("board_member", r"\bmembers? of the agency board\b|\bmember of the agency board\b"),
    ("agency_board", r"\bagency board\b"),
    ("browser_or_device_manufacturer", r"\bmanufacturer of a platform or browser or device\b"),
]
SUBJECT_WITH_MODAL_RE = re.compile(
    r"\b(?P<subject>(?:the|a|an|any|no)\s+[^.;:]{1,140}?|"
    r"members? of the agency board|the agency board|the attorney general|"
    r"the california privacy protection agency|the agency|funds)\s+"
    r"(?P<modal>shall(?: not)?|must|may(?: not)?|shall have the right to|has the right to|"
    r"have the right to|is required to|are required to|is authorized to|are authorized to)\b",
    re.IGNORECASE,
)

SECTION_METADATA: Dict[str, Dict[str, Any]] = {
    "1798.100": {"category": "notice_and_collection", "importance": 5},
    "1798.105": {"category": "consumer_rights_deletion", "importance": 5},
    "1798.106": {"category": "consumer_rights_correction", "importance": 5},
    "1798.110": {"category": "consumer_rights_access", "importance": 5},
    "1798.115": {"category": "sale_share_disclosure", "importance": 5},
    "1798.120": {"category": "opt_out_sale_share", "importance": 5},
    "1798.121": {"category": "sensitive_information_controls", "importance": 5},
    "1798.125": {"category": "nondiscrimination_financial_incentives", "importance": 5},
    "1798.130": {"category": "rights_request_handling", "importance": 5},
    "1798.135": {"category": "opt_out_mechanisms", "importance": 5},
    "1798.140": {"category": "definitions", "importance": 4},
    "1798.145": {"category": "exemptions", "importance": 4},
    "1798.146": {"category": "health_and_research_exemptions", "importance": 4},
    "1798.148": {"category": "deidentified_information", "importance": 4},
    "1798.150": {"category": "private_right_of_action", "importance": 5},
    "1798.155": {"category": "administrative_enforcement", "importance": 4},
    "1798.160": {"category": "consumer_privacy_fund", "importance": 3},
    "1798.175": {"category": "conflict_rules", "importance": 2},
    "1798.180": {"category": "preemption", "importance": 3},
    "1798.185": {"category": "rulemaking", "importance": 4},
    "1798.190": {"category": "anti_avoidance", "importance": 4},
    "1798.192": {"category": "waiver", "importance": 3},
    "1798.194": {"category": "construction", "importance": 2},
    "1798.196": {"category": "supplemental_application", "importance": 2},
    "1798.198": {"category": "operative_provisions", "importance": 2},
    "1798.199": {"category": "operative_provisions", "importance": 2},
    "1798.199.10": {"category": "agency_structure", "importance": 3},
    "1798.199.15": {"category": "agency_governance", "importance": 3},
    "1798.199.20": {"category": "agency_governance", "importance": 2},
    "1798.199.25": {"category": "agency_governance", "importance": 2},
    "1798.199.30": {"category": "agency_governance", "importance": 2},
    "1798.199.35": {"category": "agency_governance", "importance": 2},
    "1798.199.40": {"category": "agency_functions", "importance": 3},
    "1798.199.45": {"category": "agency_complaints", "importance": 3},
    "1798.199.50": {"category": "agency_hearings", "importance": 3},
    "1798.199.55": {"category": "agency_orders_and_fines", "importance": 3},
    "1798.199.60": {"category": "agency_review", "importance": 2},
    "1798.199.65": {"category": "agency_subpoena_power", "importance": 3},
    "1798.199.70": {"category": "agency_limitations_period", "importance": 2},
    "1798.199.75": {"category": "agency_civil_actions", "importance": 3},
    "1798.199.80": {"category": "agency_judgment_enforcement", "importance": 2},
    "1798.199.85": {"category": "judicial_review", "importance": 2},
    "1798.199.90": {"category": "attorney_general_enforcement", "importance": 3},
    "1798.199.95": {"category": "agency_funding_and_thresholds", "importance": 2},
    "1798.199.100": {"category": "enforcement_mitigation", "importance": 2},
}

US_FEATURE_PATTERNS: List[Tuple[str, str, re.Pattern[str]]] = [
    (
        "notice_at_collection",
        "Point-of-collection notice is a California-style disclosure trigger rather than a general lawful-basis model.",
        re.compile(r"\bat or before the point of collection\b", re.IGNORECASE),
    ),
    (
        "sale_share_framework",
        "The sell/share distinction is a U.S. state privacy construct centered on downstream data monetization and adtech disclosure.",
        re.compile(r"\bsell(?:ing|s)? or shar(?:e|es|ing)\b|\bsold or shared\b", re.IGNORECASE),
    ),
    (
        "do_not_sell_or_share_link",
        "The mandated 'Do Not Sell or Share My Personal Information' link is a distinctive California web-control artifact.",
        re.compile(r"Do Not Sell or Share My Personal Information", re.IGNORECASE),
    ),
    (
        "limit_sensitive_pi_link",
        "The 'Limit the Use of My Sensitive Personal Information' control reflects CPRA's U.S.-style consumer choice model for sensitive data.",
        re.compile(r"Limit the Use of My Sensitive Personal Information", re.IGNORECASE),
    ),
    (
        "opt_out_preference_signal",
        "Browser or device preference signals are a California-specific implementation path for opt-out rights.",
        re.compile(r"\bpreference signal\b|\bplatform or browser or device\b", re.IGNORECASE),
    ),
    (
        "verifiable_consumer_request",
        "The verifiable consumer request mechanism is a CCPA procedural concept for rights handling.",
        re.compile(r"\bverifiable consumer request\b", re.IGNORECASE),
    ),
    (
        "service_provider_contractor_model",
        "The service provider / contractor / third party split is a U.S. contractual accountability model for vendor disclosures.",
        re.compile(r"\bservice provider\b|\bcontractor\b|\bthird part(?:y|ies)\b", re.IGNORECASE),
    ),
    (
        "business_commercial_purpose_model",
        "Business purpose and commercial purpose are CCPA-specific framing concepts used instead of EU-style lawful-basis doctrine.",
        re.compile(r"\bbusiness purpose\b|\bcommercial purpose\b", re.IGNORECASE),
    ),
    (
        "cross_context_behavioral_advertising",
        "Cross-context behavioral advertising is a CPRA-specific adtech concept used to define sharing and opt-out scope.",
        re.compile(r"\bcross-context behavioral advertising\b", re.IGNORECASE),
    ),
    (
        "financial_incentives_and_loyalty",
        "Financial incentives and loyalty programs are a distinctive U.S. consumer-protection overlay within privacy law.",
        re.compile(r"\bfinancial incentive\b|\bloyalty\b|\brewards\b", re.IGNORECASE),
    ),
    (
        "private_action_security_breach_only",
        "The limited private right of action for security breaches, with statutory damages, reflects a U.S. litigation-oriented remedy model.",
        re.compile(r"\bstatutory damages\b|\bsecurity breach(?:es)?\b|\bprivate right of action\b", re.IGNORECASE),
    ),
    (
        "sectoral_exemptions_and_federalism",
        "HIPAA, CMIA, GLBA, FCRA and similar carve-outs reflect the U.S. sectoral-privacy and federalism structure.",
        re.compile(
            r"\bHIPAA\b|\bConfidentiality of Medical Information Act\b|\bGramm[- ]Leach\b|"
            r"\bFinancial Information Privacy Act\b|\bFair Credit Reporting Act\b|"
            r"\bDriver(?:'|’)s Privacy Protection Act\b|\bInsurance Code\b",
            re.IGNORECASE,
        ),
    ),
    (
        "california_resident_scope",
        "Scope keyed to California residents is a hallmark of state privacy legislation inside the broader U.S. system.",
        re.compile(r"\bCalifornia resident\b|\bCalifornia residents?\b", re.IGNORECASE),
    ),
    (
        "business_threshold_scope",
        "Entity qualification by revenue or data-volume thresholds is characteristic of U.S. state privacy statutes.",
        re.compile(
            r"\bannual gross revenues\b|\b50 percent or more of its annual revenues\b|"
            r"\b100,000 or more consumers or households\b|\b100,000 or more consumers\b",
            re.IGNORECASE,
        ),
    ),
    (
        "minors_opt_in_sale_share",
        "The under-16 sale/share opt-in rule reflects the California approach to minors in adtech and data monetization contexts.",
        re.compile(r"\bunder 16 years of age\b|\b13 years of age and less than 16 years of age\b", re.IGNORECASE),
    ),
    (
        "household_data",
        "Household data is a CCPA-specific concept that differs from most non-U.S. privacy regimes.",
        re.compile(r"\bhousehold\b", re.IGNORECASE),
    ),
    (
        "dark_patterns",
        "Dark-pattern restrictions as a validity rule for consumer choice are especially prominent in modern U.S. state privacy law.",
        re.compile(r"\bdark pattern\b", re.IGNORECASE),
    ),
    (
        "state_privacy_agency_enforcement",
        "The California Privacy Protection Agency and Attorney General split reflects U.S. state administrative enforcement design.",
        re.compile(r"\bCalifornia Privacy Protection Agency\b|\bAttorney General\b|\bthe agency\b", re.IGNORECASE),
    ),
]

NON_SUBSTANTIVE_TITLE_RE = re.compile(r"^[A-Z][A-Za-z0-9 ,/’'\"-]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a CCPA/CPRA semantic network with law -> clause -> obligation."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to the extracted CCPA/CPRA text file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output") / "CCPA_EN_TXT.semantic_network.json",
        help="Path to the generated semantic-network JSON file.",
    )
    return parser.parse_args()


def normalize_space(text: str) -> str:
    replacements = {
        "\u00a0": " ",
        "\u200b": "",
        "\ufeff": "",
        "鈥檚": "’s",
        "鈥?": "’",
        "鈥淐": "“C",
        "鈥淒": "“D",
        "鈥淗": "“H",
        "鈥淢": "“M",
        "鈥淧": "“P",
        "鈥淪": "“S",
        "鈥?": "”",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def load_lines(input_path: Path) -> List[str]:
    text = input_path.read_text(encoding="utf-8")
    lines: List[str] = []
    for raw_line in text.splitlines():
        line = normalize_space(raw_line)
        if not line:
            continue
        if PAGE_RE.match(line):
            continue
        lines.append(line)
    return lines


def find_body_start_and_section_order(lines: Sequence[str]) -> Tuple[int, List[str]]:
    matches = [index for index, line in enumerate(lines) if line.startswith("1798.100.")]
    if not matches:
        raise ValueError("Could not find Section 1798.100 in the source text.")

    body_start = matches[1] if len(matches) > 1 else matches[0]
    section_order: List[str] = []
    seen: set[str] = set()

    for line in lines[:body_start]:
        match = SECTION_RE.match(line)
        if not match:
            continue
        section_number = match.group("number")
        if section_number in seen:
            continue
        section_order.append(section_number)
        seen.add(section_number)

    if not section_order:
        for line in lines[body_start:]:
            match = SECTION_RE.match(line)
            if not match:
                continue
            section_number = match.group("number")
            if section_number in seen:
                continue
            section_order.append(section_number)
            seen.add(section_number)

    return body_start, section_order


def parse_sections(lines: List[str]) -> List[Dict[str, Any]]:
    body_start, section_order = find_body_start_and_section_order(lines)
    clauses: List[Dict[str, Any]] = []
    current_section: Optional[str] = None
    current_rest: str = ""
    current_lines: List[str] = []
    next_section_index = 0

    def flush_section() -> None:
        nonlocal current_section, current_rest, current_lines
        if current_section is None:
            return

        title, body_lines = split_section_content(current_rest, current_lines)
        clause = build_clause_record(current_section, title, body_lines)
        clauses.append(clause)
        current_section = None
        current_rest = ""
        current_lines = []

    for line in lines[body_start:]:
        match = SECTION_RE.match(line)
        expected_section = section_order[next_section_index] if next_section_index < len(section_order) else None
        if match and expected_section and match.group("number") == expected_section:
            flush_section()
            current_section = match.group("number")
            current_rest = match.group("rest")
            next_section_index += 1
            continue

        if current_section is not None:
            current_lines.append(line)

    flush_section()
    return clauses


def split_section_content(first_rest: str, content_lines: Sequence[str]) -> Tuple[str, List[str]]:
    title_lines: List[str] = []
    body_lines: List[str] = []

    if first_rest:
        if is_body_start(first_rest, title_lines):
            body_lines.append(first_rest)
        else:
            title_lines.append(first_rest)

    for line in content_lines:
        if body_lines:
            body_lines.append(line)
            continue
        if is_body_start(line, title_lines):
            body_lines.append(line)
        else:
            title_lines.append(line)

    title = " ".join(title_lines).strip()
    return title, body_lines


def is_body_start(line: str, title_lines: Sequence[str]) -> bool:
    if not line:
        return False
    if LEADING_LABELS_RE.match(line):
        return True
    if line.startswith(BODY_STARTERS):
        return True
    if line.endswith(".") and not NON_SUBSTANTIVE_TITLE_RE.match(line):
        return True
    if len(title_lines) >= 2:
        return True
    return False


def build_clause_record(section_number: str, title: str, body_lines: Sequence[str]) -> Dict[str, Any]:
    metadata = SECTION_METADATA.get(section_number, {})
    outline_nodes = parse_outline_nodes(body_lines)
    body_text = merge_body_lines(body_lines)
    us_features = detect_us_features(" ".join(filter(None, [title, body_text])))

    return {
        "clause_id": f"CCPA_SEC_{section_number.replace('.', '_')}",
        "clause_type": "section",
        "law_id": "US_CA_CCPA_CPRA_2018",
        "law_name": "California Consumer Privacy Act / CPRA",
        "jurisdiction": "US-CA",
        "section_number": section_number,
        "article_reference": f"Section {section_number}",
        "section_reference": f"Section {section_number}",
        "title": title or infer_title_from_body(body_lines),
        "category": metadata.get("category", "general"),
        "importance": metadata.get("importance", 2),
        "text": body_text,
        "outline_nodes": outline_nodes,
        "is_us_jurisdiction_specific": bool(us_features),
        "us_jurisdiction_features": [item["tag"] for item in us_features],
        "us_jurisdiction_feature_notes": [item["note"] for item in us_features],
        "obligation_ids": [],
    }


def infer_title_from_body(body_lines: Sequence[str]) -> str:
    if not body_lines:
        return ""
    first_line = body_lines[0]
    if len(first_line) <= 120 and not LEADING_LABELS_RE.match(first_line):
        return first_line.rstrip(".")
    return ""


def merge_body_lines(body_lines: Sequence[str]) -> str:
    merged: List[str] = []
    for line in body_lines:
        if LEADING_LABELS_RE.match(line):
            merged.append(line)
            continue
        if merged:
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return "\n".join(merged)


def parse_outline_nodes(body_lines: Sequence[str]) -> List[Dict[str, Any]]:
    ordered_paths: List[str] = []
    nodes_by_path: Dict[str, Dict[str, Any]] = {}
    current_path: Optional[str] = None
    stack: Dict[int, str] = {}

    def ensure_node(level: int, label: Optional[str], path: str, parent_path: Optional[str], text: str = "") -> None:
        if path in nodes_by_path:
            if text:
                existing = nodes_by_path[path]["text"]
                nodes_by_path[path]["text"] = normalize_space(f"{existing} {text}" if existing else text)
            return
        ordered_paths.append(path)
        nodes_by_path[path] = {
            "path": path,
            "level": level,
            "label": label,
            "parent_path": parent_path,
            "text": normalize_space(text),
            "children": [],
        }

    for line in body_lines:
        label_match = LEADING_LABELS_RE.match(line)
        if not label_match:
            if current_path is None:
                ensure_node(level=0, label=None, path="root", parent_path=None, text=line)
                current_path = "root"
            else:
                nodes_by_path[current_path]["text"] = normalize_space(
                    f"{nodes_by_path[current_path]['text']} {line}"
                )
            continue

        labels = LABEL_RE.findall(label_match.group("labels"))
        text = label_match.group("text").strip()
        previous_level = 0

        for index, label in enumerate(labels):
            level = infer_label_level(label, previous_level, stack)
            clear_deeper_levels(stack, level)
            stack[level] = label
            path = build_path(stack, level)
            parent_path = build_path(stack, level - 1) if level > 1 and has_path(stack, level - 1) else None
            is_last = index == len(labels) - 1
            ensure_node(level=level, label=label, path=path, parent_path=parent_path, text=text if is_last else "")
            current_path = path
            previous_level = level

    for node in nodes_by_path.values():
        parent_path = node["parent_path"]
        if parent_path and parent_path in nodes_by_path:
            nodes_by_path[parent_path]["children"].append(node["path"])

    return [nodes_by_path[path] for path in ordered_paths]


def infer_label_level(label: str, previous_level: int, stack: Dict[int, str]) -> int:
    if label.isdigit():
        level = 2
    elif label.isalpha() and label.isupper():
        level = 3
    elif is_lower_roman(label):
        if 3 in stack or previous_level >= 3:
            level = 4
        else:
            level = 1
    else:
        level = 1

    if previous_level and level <= previous_level:
        level = previous_level + 1
    return level


def is_lower_roman(value: str) -> bool:
    return bool(re.fullmatch(r"[ivxlcdm]+", value))


def clear_deeper_levels(stack: Dict[int, str], level: int) -> None:
    for key in list(stack.keys()):
        if key >= level:
            del stack[key]


def has_path(stack: Dict[int, str], level: int) -> bool:
    return all(index in stack for index in range(1, level + 1))


def build_path(stack: Dict[int, str], level: int) -> str:
    return "".join(f"({stack[index]})" for index in range(1, level + 1) if index in stack)


def split_sentences(text: str) -> List[str]:
    normalized = normalize_space(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z0-9])", normalized)
    return [part.strip() for part in parts if part.strip()]


def is_normative(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(("means ", "for purposes of this", "for purposes of this title")):
        return False
    if RIGHT_RE.search(text):
        return True
    if EXCEPTION_RE.search(text):
        return True
    if PROHIBITION_RE.search(text):
        return True
    if DUTY_RE.search(text):
        return True
    if IMPERATIVE_RE.search(text):
        return True
    if POWER_RE.search(text):
        return True
    return False


def is_contextual_stem(text: str) -> bool:
    lowered = text.lower().rstrip()
    if text.endswith(":"):
        return True
    return lowered.endswith("the following") or lowered.endswith("all of the following")


def classify_obligation(statement: str) -> str:
    if RIGHT_RE.search(statement):
        return "right"
    if EXCEPTION_RE.search(statement):
        return "exception"
    if PROHIBITION_RE.search(statement):
        return "prohibition"
    if IMPERATIVE_RE.search(statement):
        return "duty"
    if POWER_RE.search(statement) and not DUTY_RE.search(statement):
        return "power"
    return "duty"


def detect_actor(statement: str) -> str:
    subject_match = SUBJECT_WITH_MODAL_RE.search(statement)
    if subject_match:
        actor = map_subject_to_actor(subject_match.group("subject"))
        if actor:
            return actor

    lowered = statement.lower()
    for actor, pattern in ACTOR_PATTERNS:
        if re.search(pattern, lowered):
            return actor
    return "general"


def map_subject_to_actor(subject: str) -> Optional[str]:
    normalized = subject.strip().lower()
    if "business, service provider, contractor, or other person" in normalized:
        return "regulated_entity"
    if "california privacy protection agency" in normalized or normalized == "the agency":
        return "california_privacy_protection_agency"
    if "attorney general" in normalized:
        return "attorney_general"
    if "service provider" in normalized and "business" not in normalized:
        return "service_provider"
    if "contractor" in normalized and "business" not in normalized:
        return "contractor"
    if "third party" in normalized:
        return "third_party"
    if "court" in normalized:
        return "court"
    if "agency board" in normalized:
        return "agency_board"
    if "member" in normalized and "agency board" in normalized:
        return "board_member"
    if "consumer" in normalized:
        return "consumer"
    if "business" in normalized:
        return "business"
    if "manufacturer of a platform or browser or device" in normalized:
        return "browser_or_device_manufacturer"
    return None


def detect_us_features(text: str) -> List[Dict[str, str]]:
    features: List[Dict[str, str]] = []
    for tag, note, pattern in US_FEATURE_PATTERNS:
        if pattern.search(text):
            features.append({"tag": tag, "note": note})
    return features


def build_obligations(clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    obligations: List[Dict[str, Any]] = []

    for clause in clauses:
        nodes = clause["outline_nodes"]
        nodes_by_path = {node["path"]: node for node in nodes}
        obligation_index = 1
        seen: set[Tuple[str, str]] = set()

        for node in nodes:
            composed_text = compose_node_text(node, nodes_by_path)
            reference = build_source_reference(clause["section_number"], node["path"])

            if node["text"] and is_normative(node["text"]):
                for statement in split_sentences(node["text"]):
                    if not is_normative(statement):
                        continue
                    key = (reference, statement)
                    if key in seen:
                        continue
                    obligation = build_obligation_record(
                        clause=clause,
                        obligation_index=obligation_index,
                        reference=reference,
                        statement=statement,
                    )
                    obligations.append(obligation)
                    clause["obligation_ids"].append(obligation["obligation_id"])
                    seen.add(key)
                    obligation_index += 1

            if composed_text and composed_text != node["text"] and needs_context(node["text"]):
                for statement in split_sentences(composed_text):
                    if not is_normative(statement):
                        continue
                    key = (reference, statement)
                    if key in seen:
                        continue
                    obligation = build_obligation_record(
                        clause=clause,
                        obligation_index=obligation_index,
                        reference=reference,
                        statement=statement,
                    )
                    obligations.append(obligation)
                    clause["obligation_ids"].append(obligation["obligation_id"])
                    seen.add(key)
                    obligation_index += 1

        clause["obligation_ids"] = list(dict.fromkeys(clause["obligation_ids"]))

    return obligations


def compose_node_text(node: Dict[str, Any], nodes_by_path: Dict[str, Dict[str, Any]]) -> str:
    parts: List[str] = []
    lineage = build_lineage(node, nodes_by_path)
    contextual_parts: List[str] = []

    for ancestor in lineage[:-1]:
        text = ancestor["text"]
        if not text:
            continue
        if is_contextual_stem(text):
            contextual_parts.append(text.rstrip(":;"))

    if contextual_parts:
        parts.extend(contextual_parts[-2:])

    current_text = lineage[-1]["text"]
    if current_text:
        parts.append(current_text)

    return normalize_space(" ".join(parts))


def build_lineage(node: Dict[str, Any], nodes_by_path: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    lineage: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = node
    while current is not None:
        lineage.append(current)
        parent_path = current["parent_path"]
        current = nodes_by_path.get(parent_path) if parent_path else None
    lineage.reverse()
    return lineage


def needs_context(text: str) -> bool:
    normalized = normalize_space(text)
    if not normalized:
        return False
    if normalized.startswith(
        (
            "The ",
            "If ",
            "To ",
            "Selling ",
            "Retaining ",
            "Using ",
            "Disclosing ",
            "Combining ",
            "Helping ",
            "Debug",
            "Exercise ",
            "Comply ",
            "Engage ",
            "Complete ",
            "Any additional purposes",
        )
    ):
        return True
    if re.match(
        r"^(?:A|An|Any|No|This title|Subject to|On or before|Beginning|There is|Whenever|"
        r"Members|Ensure|Provide|Include|Use|Display|Permit|Grant|Require|Notify|Disclose|"
        r"Make|Honor|Allow|Delete|Correct|Cooperate|Maintain|Complete|Help|Debug|Exercise|"
        r"Comply|Engage|Take|Protect|Stop|Remediate|Specify|Issue|Update|Review|Promote|"
        r"Solicit|Monitor|Administer)\b",
        normalized,
        re.IGNORECASE,
    ):
        return False
    return True


def build_source_reference(section_number: str, path: str) -> str:
    if path == "root":
        return f"Section {section_number}"
    return f"Section {section_number}{path}"


def build_obligation_record(
    clause: Dict[str, Any],
    obligation_index: int,
    reference: str,
    statement: str,
) -> Dict[str, Any]:
    statement_features = detect_us_features(statement)
    return {
        "obligation_id": f"{clause['clause_id']}_OBL_{obligation_index}",
        "law_id": clause["law_id"],
        "clause_id": clause["clause_id"],
        "jurisdiction": clause["jurisdiction"],
        "article_reference": clause["article_reference"],
        "source_reference": reference,
        "category": clause["category"],
        "type": classify_obligation(statement),
        "actor": detect_actor(statement),
        "statement": statement,
        "is_us_jurisdiction_specific": bool(statement_features or clause["is_us_jurisdiction_specific"]),
        "us_jurisdiction_features": [item["tag"] for item in statement_features],
    }


def build_law_record(input_path: Path, clause_count: int, obligation_count: int) -> Dict[str, Any]:
    return {
        "law_id": "US_CA_CCPA_CPRA_2018",
        "code": "CCPA/CPRA",
        "name": "California Consumer Privacy Act / CPRA",
        "official_title": "California Consumer Privacy Act of 2018 as amended by the California Privacy Rights Act",
        "jurisdiction": "US-CA",
        "model": "law -> clause -> obligation",
        "source_file": str(input_path),
        "clause_count": clause_count,
        "obligation_count": obligation_count,
    }


def build_relations(law_id: str, clauses: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
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
    law: Dict[str, Any], clauses: Sequence[Dict[str, Any]], obligations: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    type_counts = Counter(item["type"] for item in obligations)
    actor_counts = Counter(item["actor"] for item in obligations)
    category_counts = Counter(item["category"] for item in clauses)
    feature_counts = Counter(
        feature for clause in clauses for feature in clause.get("us_jurisdiction_features", [])
    )
    key_clause_refs = [
        clause["section_reference"]
        for clause in clauses
        if clause.get("importance", 0) >= 5 or clause.get("us_jurisdiction_features")
    ]

    return {
        "law_id": law["law_id"],
        "clauses_by_category": dict(category_counts),
        "obligations_by_type": dict(type_counts),
        "obligations_by_actor": dict(actor_counts.most_common(12)),
        "us_specific_clause_count": sum(1 for clause in clauses if clause["is_us_jurisdiction_specific"]),
        "us_feature_counts": dict(feature_counts),
        "key_clauses": key_clause_refs,
    }


def build_semantic_network(input_path: Path) -> Dict[str, Any]:
    lines = load_lines(input_path)
    clauses = parse_sections(lines)
    obligations = build_obligations(clauses)
    law = build_law_record(
        input_path=input_path,
        clause_count=len(clauses),
        obligation_count=len(obligations),
    )
    relations = build_relations(law_id=law["law_id"], clauses=clauses)
    summary = add_summary(law=law, clauses=clauses, obligations=obligations)
    return {
        "law": law,
        "clauses": clauses,
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
