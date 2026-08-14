from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ARTICLE_RE = re.compile(r"^《中华人民共和国个人信息保护法》第(?P<number>[一二三四五六七八九十百零〇两]+)条：(?P<text>.*)$")
ITEM_RE = re.compile(r"^（(?P<code>[一二三四五六七八九十]+)）(?P<text>.*)$")

RIGHT_RE = re.compile(r"(?:有权|可以要求|可依法向人民法院提起诉讼)")
EXCEPTION_RE = re.compile(r"(?:可以不|不适用|除外|从其规定)")
PROHIBITION_RE = re.compile(r"(?:不得|禁止)")
CONDITION_RE = re.compile(r"(?:方可)")
POWER_RE = re.compile(r"(?:可以)")
DUTY_RE = re.compile(r"(?:应当|应立即|应在|负责|履行|报送|统筹协调|建立健全|建立|制定|指定|进行|采取|通知|公开|公布|调查|处理|推进|开展|组织|指导|监督)")

DEFINITION_RE = re.compile(r"(?:是指|是以|是.+有关的各种信息|包括)")
PUNCTUATION_END_RE = re.compile(r"[。；：]$")

ACTOR_MODAL_PATTERNS: List[Tuple[str, str]] = [
    ("large_platform_operator", r"提供重要互联网平台服务、用户数量巨大、业务类型复杂的个人信息处理者[^。；]{0,80}?(?:应当|不得|可以|负责)"),
    ("processor", r"个人信息处理者[^。；]{0,80}?(?:应当|不得|可以|方可|负责)"),
    ("trustee", r"受托人[^。；]{0,80}?(?:应当|不得|可以|负责)"),
    ("recipient", r"(?:境外接收方|接收方)[^。；]{0,80}?(?:应当|不得|可以|负责)"),
    ("cii_operator", r"关键信息基础设施运营者[^。；]{0,80}?(?:应当|不得|可以|负责)"),
    ("individual_processor_or_org", r"任何组织、个人[^。；]{0,80}?(?:应当|不得|可以|有权)"),
    ("competent_department", r"履行个人信息保护职责的部门[^。；]{0,80}?(?:应当|不得|可以|负责|履行)"),
    ("cac", r"国家网信部门[^。；]{0,80}?(?:应当|不得|可以|负责|统筹协调|推进)"),
    ("state_council_department", r"国务院有关部门[^。；]{0,80}?(?:应当|不得|可以|负责)"),
    ("local_government_department", r"县级以上地方人民政府有关部门[^。；]{0,80}?(?:应当|不得|可以|负责)"),
    ("prc_competent_authority", r"中华人民共和国主管机关[^。；]{0,80}?(?:应当|不得|可以|负责|处理)"),
    ("public_affairs_organization", r"具有管理公共事务职能的组织[^。；]{0,80}?(?:应当|不得|可以|负责|适用)"),
    ("state_organ", r"国家机关[^。；]{0,80}?(?:应当|不得|可以|负责|适用)"),
    ("foreign_org_or_individual", r"境外的组织、个人[^。；]{0,80}?(?:应当|不得|可以)"),
    ("close_relative", r"近亲属[^。；]{0,80}?(?:可以|有权)"),
    ("people_procuratorate", r"人民检察院[^。；]{0,80}?(?:可以|有权)"),
    ("consumer_organization", r"消费者组织[^。；]{0,80}?(?:可以|有权)"),
    ("individual", r"个人[^信息][^。；]{0,40}?(?:有权|可以要求|请求|撤回|发现)"),
    ("state", r"^国家[^。；]{0,80}?(?:建立健全|积极参与|促进|推动)"),
]

ACTOR_PATTERNS: List[Tuple[str, str]] = [
    ("large_platform_operator", r"提供重要互联网平台服务、用户数量巨大、业务类型复杂的个人信息处理者"),
    ("processor", r"个人信息处理者"),
    ("trustee", r"受托人"),
    ("recipient", r"^接收方|^境外接收方"),
    ("cii_operator", r"关键信息基础设施运营者"),
    ("individual_processor_or_org", r"任何组织、个人"),
    ("competent_department", r"履行个人信息保护职责的部门"),
    ("cac", r"国家网信部门"),
    ("state_council_department", r"国务院有关部门"),
    ("local_government_department", r"县级以上地方人民政府有关部门"),
    ("prc_competent_authority", r"中华人民共和国主管机关"),
    ("public_affairs_organization", r"具有管理公共事务职能的组织"),
    ("state_organ", r"国家机关"),
    ("foreign_org_or_individual", r"境外的组织、个人"),
    ("close_relative", r"近亲属"),
    ("people_procuratorate", r"人民检察院"),
    ("consumer_organization", r"消费者组织"),
    ("individual", r"^个人有权|^个人可以要求|^个人请求|^个人发现|^个人撤回|个人可以依法向人民法院提起诉讼"),
    ("state", r"^国家"),
]

CHINA_FEATURE_PATTERNS: List[Tuple[str, str, re.Pattern[str]]] = [
    (
        "separate_consent_model",
        "“单独同意/书面同意”作为多类高风险处理的法定门槛，是中国个人信息保护法中的典型制度设计。",
        re.compile(r"单独同意|书面同意"),
    ),
    (
        "under_14_minor_threshold",
        "将不满十四周岁未成年人的个人信息纳入敏感个人信息并要求监护人同意，是中国法具有辨识度的年龄门槛设计。",
        re.compile(r"不满十四周岁|十四周岁未成年人"),
    ),
    (
        "state_organs_special_regime",
        "国家机关及受授权公共事务组织适用特别规则，体现了中国法对公权力处理个人信息的专门规制。",
        re.compile(r"国家机关|管理公共事务职能的组织"),
    ),
    (
        "data_localization_and_cac_security_assessment",
        "境内存储要求与国家网信部门安全评估相结合，是中国跨境个人信息治理的核心特色。",
        re.compile(r"境内存储|境内收集和产生的个人信息存储在境内|国家网信部门组织的安全评估|关键信息基础设施运营者"),
    ),
    (
        "cac_certification_or_standard_contract",
        "个人信息保护认证、标准合同和网信部门规则共同构成中国个人信息出境的合规路径。",
        re.compile(r"个人信息保护认证|标准合同|国家网信部门"),
    ),
    (
        "foreign_law_enforcement_request_blocking",
        "向外国司法或执法机构提供境内存储个人信息须经中国主管机关批准，体现数据主权导向。",
        re.compile(r"外国司法或者执法机构|非经中华人民共和国主管机关批准"),
    ),
    (
        "reciprocal_countermeasures",
        "限制清单与对等反制条款体现了中国法在跨境数据保护中的主权与反制机制。",
        re.compile(r"限制或者禁止个人信息提供清单|对等采取措施|歧视性的禁止、限制"),
    ),
    (
        "domestic_representative_for_extraterritorial_processors",
        "域外处理者应在境内设立专门机构或指定代表，是中国法域外适用落地机制的重要组成部分。",
        re.compile(r"境内设立专门机构或者指定代表"),
    ),
    (
        "important_platform_governance",
        "对重要互联网平台服务提供者设置独立机构、平台规则和社会责任报告等义务，体现中国平台治理特色。",
        re.compile(r"重要互联网平台服务|用户数量巨大|业务类型复杂|社会责任报告|主要由外部成员组成的独立机构"),
    ),
    (
        "public_security_imagery_rule",
        "公共场所图像采集和身份识别设备只能为维护公共安全所必需，体现中国治安场景下的专项规则。",
        re.compile(r"公共场所安装图像采集|维护公共安全|身份识别设备"),
    ),
    (
        "social_credit_publicity",
        "违法行为记入信用档案并公示，带有中国监管体系中的信用治理色彩。",
        re.compile(r"记入信用档案|予以公示"),
    ),
    (
        "multi_agency_cac_supervision",
        "由国家网信部门统筹、国务院有关部门和地方部门分工负责，体现中国多层级监管结构。",
        re.compile(r"国家网信部门负责统筹协调|国务院有关部门|县级以上地方人民政府有关部门"),
    ),
    (
        "national_security_and_public_interest_limit",
        "将国家安全、公共利益纳入个人信息处理边界，是中国法中较为鲜明的公法约束表达。",
        re.compile(r"国家安全|公共利益"),
    ),
    (
        "procuratorate_public_interest_litigation",
        "人民检察院和法定组织提起公益诉讼，是中国公私法救济结合的特色路径。",
        re.compile(r"人民检察院|公益诉讼"),
    ),
]

ARTICLE_TITLES: Dict[int, str] = {
    1: "立法目的",
    2: "个人信息权益受保护",
    3: "适用范围与域外适用",
    4: "个人信息与处理定义",
    5: "合法正当必要诚信原则",
    6: "目的限定与最小必要",
    7: "公开透明原则",
    8: "信息质量原则",
    9: "处理者责任与安全保障",
    10: "非法处理禁止",
    11: "国家保护制度",
    12: "国际规则参与与互认",
    13: "处理个人信息的合法条件",
    14: "同意有效条件与重新同意",
    15: "撤回同意",
    16: "不得以不同意为由拒绝非必要服务",
    17: "处理前告知义务",
    18: "告知例外与事后告知",
    19: "最短保存期限",
    20: "共同处理责任",
    21: "委托处理与受托监督",
    22: "因组织变更转移个人信息",
    23: "向其他处理者提供信息",
    24: "自动化决策规则",
    25: "公开个人信息限制",
    26: "公共场所图像与身份识别",
    27: "已公开个人信息处理",
    28: "敏感个人信息定义与处理条件",
    29: "敏感个人信息单独同意",
    30: "敏感个人信息特别告知",
    31: "不满十四周岁未成年人信息",
    32: "敏感信息处理特别许可或限制",
    33: "国家机关适用规则",
    34: "国家机关处理边界",
    35: "国家机关告知义务例外",
    36: "国家机关境内存储与出境评估",
    37: "授权公共事务组织适用",
    38: "个人信息出境条件",
    39: "出境单独同意与告知",
    40: "关键信息基础设施和大规模处理者本地存储",
    41: "外国司法执法请求审批",
    42: "境外侵权主体限制清单",
    43: "对等反制措施",
    44: "个人的知情决定与拒绝权",
    45: "查阅复制与转移权",
    46: "更正补充权",
    47: "删除权",
    48: "规则解释说明权",
    49: "近亲属对死者信息权利",
    50: "权利申请机制与诉讼",
    51: "安全保障措施",
    52: "个人信息保护负责人",
    53: "境外处理者境内机构或代表",
    54: "定期合规审计",
    55: "个人信息保护影响评估触发",
    56: "影响评估内容与留存",
    57: "安全事件补救与通知",
    58: "重要互联网平台特别义务",
    59: "受托人安全保障与协助义务",
    60: "监管部门体系",
    61: "监管部门职责",
    62: "国家网信部门推进工作",
    63: "监管调查措施",
    64: "风险约谈与整改",
    65: "投诉举报与联系方式公布",
    66: "一般违法处理与高额罚款",
    67: "记入信用档案并公示",
    68: "国家机关违法责任",
    69: "侵权赔偿责任倒置",
    70: "公益诉讼",
    71: "治安管理处罚与刑责",
    72: "个人家庭事务例外与特别法适用",
    73: "术语定义",
    74: "生效日期",
}

KEY_ARTICLES = {
    3,
    6,
    13,
    14,
    17,
    21,
    23,
    24,
    28,
    29,
    31,
    36,
    38,
    39,
    40,
    41,
    42,
    43,
    44,
    45,
    47,
    50,
    51,
    52,
    53,
    55,
    57,
    58,
    60,
    63,
    64,
    66,
    69,
    70,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a PIPL semantic network with law -> clause -> obligation."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=Path("output") / "个人信息保护法.txt",
        help="Path to the extracted PIPL text file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output") / "个人信息保护法.semantic_network.json",
        help="Path to the generated semantic-network JSON file.",
    )
    return parser.parse_args()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_lines(input_path: Path) -> List[str]:
    text = input_path.read_text(encoding="utf-8")
    return [normalize_space(line) for line in text.splitlines() if normalize_space(line)]


def chinese_numeral_to_int(value: str) -> int:
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        tens = 1 if not left else digits[left]
        ones = 0 if not right else digits[right]
        return tens * 10 + ones
    return digits[value]


def get_chapter_metadata(article_number: int) -> Dict[str, Optional[str]]:
    if 1 <= article_number <= 12:
        return {
            "chapter_code": "第一章",
            "chapter_title": "总则",
            "section_code": None,
            "section_title": None,
        }
    if 13 <= article_number <= 27:
        return {
            "chapter_code": "第二章",
            "chapter_title": "个人信息处理规则",
            "section_code": "第一节",
            "section_title": "一般规定",
        }
    if 28 <= article_number <= 32:
        return {
            "chapter_code": "第二章",
            "chapter_title": "个人信息处理规则",
            "section_code": "第二节",
            "section_title": "敏感个人信息的处理规则",
        }
    if 33 <= article_number <= 37:
        return {
            "chapter_code": "第二章",
            "chapter_title": "个人信息处理规则",
            "section_code": "第三节",
            "section_title": "国家机关处理个人信息的特别规定",
        }
    if 38 <= article_number <= 43:
        return {
            "chapter_code": "第三章",
            "chapter_title": "个人信息跨境提供的规则",
            "section_code": None,
            "section_title": None,
        }
    if 44 <= article_number <= 50:
        return {
            "chapter_code": "第四章",
            "chapter_title": "个人在个人信息处理活动中的权利",
            "section_code": None,
            "section_title": None,
        }
    if 51 <= article_number <= 59:
        return {
            "chapter_code": "第五章",
            "chapter_title": "个人信息处理者的义务",
            "section_code": None,
            "section_title": None,
        }
    if 60 <= article_number <= 65:
        return {
            "chapter_code": "第六章",
            "chapter_title": "履行个人信息保护职责的部门",
            "section_code": None,
            "section_title": None,
        }
    if 66 <= article_number <= 71:
        return {
            "chapter_code": "第七章",
            "chapter_title": "法律责任",
            "section_code": None,
            "section_title": None,
        }
    return {
        "chapter_code": "第八章",
        "chapter_title": "附则",
        "section_code": None,
        "section_title": None,
    }


def get_category(article_number: int) -> str:
    if 1 <= article_number <= 4:
        return "general_provisions"
    if 5 <= article_number <= 10:
        return "core_principles"
    if 11 <= article_number <= 12:
        return "state_governance"
    if 13 <= article_number <= 16:
        return "lawful_basis_and_consent"
    if 17 <= article_number <= 19:
        return "transparency_and_retention"
    if 20 <= article_number <= 23:
        return "controller_relationships"
    if 24 <= article_number <= 27:
        return "special_processing_rules"
    if 28 <= article_number <= 32:
        return "sensitive_and_minors"
    if 33 <= article_number <= 37:
        return "state_organs"
    if 38 <= article_number <= 43:
        return "cross_border_transfer"
    if 44 <= article_number <= 50:
        return "individual_rights"
    if 51 <= article_number <= 59:
        return "accountability_and_security"
    if 60 <= article_number <= 65:
        return "regulatory_enforcement"
    if 66 <= article_number <= 71:
        return "liabilities_and_remedies"
    return "supplementary"


def get_importance(article_number: int, category: str, china_features: Sequence[Dict[str, str]]) -> int:
    category_importance = {
        "general_provisions": 2,
        "core_principles": 4,
        "state_governance": 3,
        "lawful_basis_and_consent": 5,
        "transparency_and_retention": 4,
        "controller_relationships": 4,
        "special_processing_rules": 4,
        "sensitive_and_minors": 5,
        "state_organs": 4,
        "cross_border_transfer": 5,
        "individual_rights": 5,
        "accountability_and_security": 5,
        "regulatory_enforcement": 4,
        "liabilities_and_remedies": 4,
        "supplementary": 1,
    }
    importance = category_importance.get(category, 2)
    if article_number in KEY_ARTICLES:
        importance = max(importance, 5)
    if china_features and importance < 4:
        importance = 4
    return importance


def detect_china_features(text: str) -> List[Dict[str, str]]:
    features: List[Dict[str, str]] = []
    for tag, note, pattern in CHINA_FEATURE_PATTERNS:
        if pattern.search(text):
            features.append({"tag": tag, "note": note})
    return features


def merge_wrapped_lines(lines: Sequence[str]) -> List[str]:
    merged: List[str] = []
    for line in lines:
        if not line:
            continue
        if ITEM_RE.match(line):
            merged.append(line)
            continue
        if not merged:
            merged.append(line)
            continue
        if not PUNCTUATION_END_RE.search(merged[-1]):
            merged[-1] = normalize_space(f"{merged[-1]} {line}")
            continue
        merged.append(line)
    return merged


def parse_articles(lines: Sequence[str]) -> List[Dict[str, Any]]:
    articles: List[Dict[str, Any]] = []
    current_article_number: Optional[int] = None
    current_body_lines: List[str] = []

    def flush_article() -> None:
        nonlocal current_article_number, current_body_lines
        if current_article_number is None:
            return

        raw_body_lines = merge_wrapped_lines(current_body_lines)
        body_text = "\n".join(raw_body_lines)
        chapter = get_chapter_metadata(current_article_number)
        category = get_category(current_article_number)
        china_features = detect_china_features(body_text)
        importance = get_importance(current_article_number, category, china_features)
        clause_id = f"CN_PIPL_ART_{current_article_number}"

        articles.append(
            {
                "clause_id": clause_id,
                "clause_type": "article",
                "law_id": "CN_PIPL_2021",
                "law_name": "Personal Information Protection Law",
                "law_name_local": "中华人民共和国个人信息保护法",
                "jurisdiction": "CN",
                "article_number": current_article_number,
                "article_reference": f"Article {current_article_number}",
                "article_reference_local": f"第{current_article_number}条",
                "title": ARTICLE_TITLES[current_article_number],
                "category": category,
                "importance": importance,
                "is_key_clause": current_article_number in KEY_ARTICLES,
                "chapter_code": chapter["chapter_code"],
                "chapter_title": chapter["chapter_title"],
                "section_code": chapter["section_code"],
                "section_title": chapter["section_title"],
                "text": body_text,
                "raw_body_lines": raw_body_lines,
                "is_china_jurisdiction_specific": bool(china_features),
                "china_jurisdiction_features": [item["tag"] for item in china_features],
                "china_jurisdiction_feature_notes": [item["note"] for item in china_features],
                "obligation_ids": [],
            }
        )
        current_article_number = None
        current_body_lines = []

    for line in lines:
        match = ARTICLE_RE.match(line)
        if match:
            flush_article()
            current_article_number = chinese_numeral_to_int(match.group("number"))
            current_body_lines = [match.group("text")]
            continue
        if current_article_number is not None:
            current_body_lines.append(line)

    flush_article()
    return articles


def parse_paragraphs(article: Dict[str, Any]) -> List[Dict[str, Any]]:
    paragraphs: List[Dict[str, Any]] = []
    current_lead = ""
    current_items: List[Dict[str, str]] = []

    def flush_paragraph() -> None:
        nonlocal current_lead, current_items
        if not current_lead and not current_items:
            return
        paragraphs.append(
            {
                "paragraph_number": None,
                "lead_text": current_lead,
                "items": current_items,
            }
        )
        current_lead = ""
        current_items = []

    for line in article["raw_body_lines"]:
        item_match = ITEM_RE.match(line)
        if item_match:
            current_items.append(
                {
                    "item_code": item_match.group("code"),
                    "text": item_match.group("text"),
                }
            )
            continue

        if current_lead or current_items:
            flush_paragraph()
        current_lead = line

    flush_paragraph()
    return paragraphs


def split_sentences(text: str) -> List[str]:
    normalized = normalize_space(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。；])\s*", normalized)
    sentences = [part.strip().rstrip("；。") for part in parts if part.strip()]
    return [sentence for sentence in sentences if sentence]


def is_definition_statement(statement: str) -> bool:
    if "本法自2021年11月1日起施行" in statement:
        return False
    if RIGHT_RE.search(statement) or EXCEPTION_RE.search(statement):
        return False
    if PROHIBITION_RE.search(statement) or CONDITION_RE.search(statement):
        return False
    if DUTY_RE.search(statement) or POWER_RE.search(statement):
        return False
    return bool(DEFINITION_RE.search(statement))


def is_normative(statement: str) -> bool:
    if not statement:
        return False
    if is_definition_statement(statement):
        return False
    if RIGHT_RE.search(statement):
        return True
    if EXCEPTION_RE.search(statement):
        return True
    if PROHIBITION_RE.search(statement):
        return True
    if CONDITION_RE.search(statement):
        return True
    if DUTY_RE.search(statement):
        return True
    if POWER_RE.search(statement):
        return True
    return False


def is_contextual_stem(text: str) -> bool:
    normalized = normalize_space(text)
    return normalized.endswith("：") or "下列" in normalized or normalized.endswith("如下")


def compose_item_statement(lead_text: str, item_text: str) -> str:
    lead_prefix = normalize_space(lead_text.rstrip("：；"))
    if not lead_prefix:
        return normalize_space(item_text)
    return normalize_space(f"{lead_prefix} {item_text}")


def classify_obligation(statement: str) -> str:
    if RIGHT_RE.search(statement):
        return "right"
    if EXCEPTION_RE.search(statement):
        return "exception"
    if PROHIBITION_RE.search(statement):
        return "prohibition"
    if CONDITION_RE.search(statement):
        return "condition"
    if POWER_RE.search(statement) and not DUTY_RE.search(statement):
        return "power"
    return "duty"


def detect_actor(statement: str) -> str:
    for actor, pattern in ACTOR_MODAL_PATTERNS:
        if re.search(pattern, statement):
            return actor
    for actor, pattern in ACTOR_PATTERNS:
        if re.search(pattern, statement):
            return actor
    return "general"


def build_source_reference(
    article_number: int,
    item_code: Optional[str],
) -> str:
    if item_code:
        return f"第{article_number}条（{item_code}）"
    return f"第{article_number}条"


def build_obligation_record(
    article: Dict[str, Any],
    obligation_index: int,
    reference: str,
    statement: str,
) -> Dict[str, Any]:
    statement_features = detect_china_features(statement)
    return {
        "obligation_id": f"{article['clause_id']}_OBL_{obligation_index}",
        "law_id": article["law_id"],
        "clause_id": article["clause_id"],
        "jurisdiction": article["jurisdiction"],
        "article_reference": article["article_reference"],
        "article_reference_local": article["article_reference_local"],
        "source_reference": reference,
        "category": article["category"],
        "type": classify_obligation(statement),
        "actor": detect_actor(statement),
        "statement": statement,
        "is_china_jurisdiction_specific": bool(statement_features or article["is_china_jurisdiction_specific"]),
        "china_jurisdiction_features": [item["tag"] for item in statement_features],
    }


def build_obligations(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    obligations: List[Dict[str, Any]] = []

    for article in articles:
        article["paragraphs"] = parse_paragraphs(article)
        obligation_index = 1
        seen: set[Tuple[str, str]] = set()

        for paragraph in article["paragraphs"]:
            lead_text = paragraph["lead_text"]
            items = paragraph["items"]

            if lead_text:
                reference = build_source_reference(article["article_number"], None)
                for statement in split_sentences(lead_text):
                    if not is_normative(statement):
                        continue
                    key = (reference, statement)
                    if key in seen:
                        continue
                    obligation = build_obligation_record(
                        article=article,
                        obligation_index=obligation_index,
                        reference=reference,
                        statement=statement,
                    )
                    obligations.append(obligation)
                    article["obligation_ids"].append(obligation["obligation_id"])
                    seen.add(key)
                    obligation_index += 1

            for item in items:
                reference = build_source_reference(article["article_number"], item["item_code"])
                candidate_text = (
                    compose_item_statement(lead_text, item["text"])
                    if lead_text and is_contextual_stem(lead_text)
                    else item["text"]
                )
                for statement in split_sentences(candidate_text):
                    if not is_normative(statement):
                        continue
                    key = (reference, statement)
                    if key in seen:
                        continue
                    obligation = build_obligation_record(
                        article=article,
                        obligation_index=obligation_index,
                        reference=reference,
                        statement=statement,
                    )
                    obligations.append(obligation)
                    article["obligation_ids"].append(obligation["obligation_id"])
                    seen.add(key)
                    obligation_index += 1

        article["obligation_ids"] = list(dict.fromkeys(article["obligation_ids"]))

    return obligations


def build_law_record(input_path: Path, clause_count: int, obligation_count: int) -> Dict[str, Any]:
    return {
        "law_id": "CN_PIPL_2021",
        "code": "PIPL",
        "name": "Personal Information Protection Law",
        "official_title": "中华人民共和国个人信息保护法",
        "jurisdiction": "CN",
        "language": "zh-CN",
        "effective_date": "2021-11-01",
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
        for obligation_id in clause["obligation_ids"]:
            relations.append(
                {
                    "source": clause["clause_id"],
                    "target": obligation_id,
                    "relation": "imposes_obligation",
                }
            )
    return relations


def add_summary(
    law: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    obligations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    type_counts = Counter(item["type"] for item in obligations)
    actor_counts = Counter(item["actor"] for item in obligations)
    category_counts = Counter(item["category"] for item in clauses)
    feature_counts = Counter(
        feature for clause in clauses for feature in clause.get("china_jurisdiction_features", [])
    )
    key_clauses = [
        {
            "article_reference_local": clause["article_reference_local"],
            "title": clause["title"],
            "category": clause["category"],
        }
        for clause in clauses
        if clause["is_key_clause"] or clause["is_china_jurisdiction_specific"]
    ]

    return {
        "law_id": law["law_id"],
        "clauses_by_category": dict(category_counts),
        "obligations_by_type": dict(type_counts),
        "obligations_by_actor": dict(actor_counts.most_common(12)),
        "china_specific_clause_count": sum(
            1 for clause in clauses if clause["is_china_jurisdiction_specific"]
        ),
        "china_feature_counts": dict(feature_counts),
        "key_clauses": key_clauses,
    }


def build_semantic_network(input_path: Path) -> Dict[str, Any]:
    lines = load_lines(input_path)
    clauses = parse_articles(lines)
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
