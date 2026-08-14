"""
Knowledge Graph Schema Normalizer
Converts PIPL_CN.json, GDPR_EN_TXT.semantic_network.json,
and CCPA_EN_TXT.semantic_network.json to unified schema.

Unified schema decisions:
- Short labels (title, chapter_title, etc.): i18n object {"zh": ..., "en": ...}
- Long text (text, statement): parallel fields + text_en + text_en_source
- Repeated enums (actor, type, category): EN enum values, translated via vocabulary table
- Jurisdiction-specific flags: normalized to jurisdiction_specific nested object
- New top-level: vocabulary, cross_jurisdiction_links (empty scaffold)
"""

import json
import copy
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_OUTPUT_DIR = PROJECT_ROOT / "output" / "normalized"


try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ---------------------------------------------------------------------------
# Vocabulary table (EN enums → i18n labels)
# ---------------------------------------------------------------------------

VOCABULARY = {
    "obligation_types": {
        "duty":        {"zh": "义务",   "en": "Duty"},
        "right":       {"zh": "权利",   "en": "Right"},
        "prohibition": {"zh": "禁止",   "en": "Prohibition"},
        "power":       {"zh": "授权",   "en": "Power"},
        "permission":  {"zh": "许可",   "en": "Permission"},
        "obligation":  {"zh": "义务",   "en": "Obligation"},
    },
    "actors": {
        "controller":              {"zh": "个人信息处理者", "en": "Controller"},
        "processor":               {"zh": "受托处理者",     "en": "Processor"},
        "data_subject":            {"zh": "个人",           "en": "Data Subject"},
        "supervisory_authority":   {"zh": "监管机构",       "en": "Supervisory Authority"},
        "third_party":             {"zh": "第三方",         "en": "Third Party"},
        "recipient":               {"zh": "接收方",         "en": "Recipient"},
        "business":                {"zh": "企业",           "en": "Business"},
        "service_provider":        {"zh": "服务提供者",     "en": "Service Provider"},
        "consumer":                {"zh": "消费者",         "en": "Consumer"},
    },
    "categories": {
        "lawful_basis":            {"zh": "合法性基础",   "en": "Lawful Basis"},
        "transparency":            {"zh": "透明度",       "en": "Transparency"},
        "data_subject_rights":     {"zh": "个人权利",     "en": "Data Subject Rights"},
        "security":                {"zh": "安全保障",     "en": "Security"},
        "cross_border":            {"zh": "跨境传输",     "en": "Cross-border Transfer"},
        "consent":                 {"zh": "同意",         "en": "Consent"},
        "accountability":          {"zh": "问责制",       "en": "Accountability"},
        "data_minimization":       {"zh": "数据最小化",   "en": "Data Minimization"},
        "purpose_limitation":      {"zh": "目的限制",     "en": "Purpose Limitation"},
        "storage_limitation":      {"zh": "存储限制",     "en": "Storage Limitation"},
        "sensitive_data":          {"zh": "敏感个人信息", "en": "Sensitive Data"},
        "enforcement":             {"zh": "执法与处罚",   "en": "Enforcement"},
        "governance":              {"zh": "治理",         "en": "Governance"},
        "notification":            {"zh": "通知义务",     "en": "Notification"},
        "general":                 {"zh": "一般规定",     "en": "General Provisions"},
    },
    "jurisdictions": {
        "CN": {"zh": "中国", "en": "China"},
        "EU": {"zh": "欧盟", "en": "European Union"},
        "US": {"zh": "美国（加利福尼亚州）", "en": "United States (California)"},
    }
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def i18n(zh=None, en=None):
    """Create an i18n object. None values kept as None."""
    return {"zh": zh, "en": en}


def ensure_i18n(value, lang_hint="en"):
    """
    If value is already a dict with zh/en keys, return as-is.
    If it's a plain string, wrap it in i18n with the appropriate lang key.
    """
    if value is None:
        return i18n()
    if isinstance(value, dict) and ("zh" in value or "en" in value):
        return value
    if isinstance(value, str):
        if lang_hint == "zh":
            return i18n(zh=value, en=None)
        return i18n(zh=None, en=value)
    return i18n()


def normalize_paragraphs(paragraphs):
    """Ensure paragraphs match unified schema."""
    if not paragraphs:
        return []
    result = []
    for p in paragraphs:
        result.append({
            "paragraph_number": p.get("paragraph_number"),
            "lead_text": p.get("lead_text"),
            "items": [
                {"item_code": item.get("item_code"), "text": item.get("text")}
                for item in (p.get("items") or [])
            ]
        })
    return result


def normalize_relations(relations):
    if not relations:
        return []
    return [
        {"source": r.get("source"), "target": r.get("target"), "relation": r.get("relation")}
        for r in relations
    ]


def make_jurisdiction_specific(is_specific, features, feature_notes=None):
    """Normalize jurisdiction_specific from any source format."""
    return {
        "is_specific": bool(is_specific) if is_specific is not None else False,
        "features": features or [],
        "feature_notes": feature_notes or []
    }

# ---------------------------------------------------------------------------
# PIPL normalizer  (source language: ZH)
# ---------------------------------------------------------------------------

def normalize_pipl(data: dict) -> dict:
    law_raw = data.get("law", {})

    law = {
        "law_id":          law_raw.get("law_id", "PIPL"),
        "code":            law_raw.get("code", "PIPL"),
        "name":            law_raw.get("name"),
        "official_title":  law_raw.get("official_title"),
        "jurisdiction":    law_raw.get("jurisdiction", "CN"),
        "language":        law_raw.get("language", "ZH"),
        "effective_date":  law_raw.get("effective_date", "2021-11-01"),
        "model":           law_raw.get("model"),
        "source_file":     law_raw.get("source_file"),
        "clause_count":    law_raw.get("clause_count", 0),
        "obligation_count":law_raw.get("obligation_count", 0),
    }

    clauses = []
    for c in (data.get("clauses") or []):
        # title → i18n (ZH source, EN pending)
        title_zh = c.get("title") or c.get("law_name_local")
        title_en = None  # to be translated

        # chapter / section titles → i18n
        chapter_title_zh = c.get("chapter_title")
        section_title_zh = c.get("section_title")

        # jurisdiction_specific
        js = make_jurisdiction_specific(
            c.get("is_china_jurisdiction_specific"),
            c.get("china_jurisdiction_features"),
            c.get("china_jurisdiction_feature_notes"),
        )

        clauses.append({
            "clause_id":               c.get("clause_id"),
            "clause_type":             c.get("clause_type"),
            "law_id":                  c.get("law_id"),
            "law_name":                c.get("law_name"),
            "law_name_local":          c.get("law_name_local"),
            "jurisdiction":            c.get("jurisdiction", "CN"),
            "article_number":          c.get("article_number"),
            "article_reference":       c.get("article_reference"),
            "article_reference_local": c.get("article_reference_local"),
            "alt_references": {
                "section_number":    None,
                "section_reference": None,
            },
            "title":               i18n(zh=title_zh, en=title_en),
            "category":            c.get("category"),
            "importance":          c.get("importance"),
            "is_key_clause":       c.get("is_key_clause"),
            "chapter_code":        c.get("chapter_code"),
            "chapter_title":       i18n(zh=chapter_title_zh, en=None),
            "section_code":        c.get("section_code"),
            "section_title":       i18n(zh=section_title_zh, en=None),
            "text":                c.get("text"),
            "text_en":             None,
            "text_en_source":      "pending",
            "paragraphs":          normalize_paragraphs(c.get("paragraphs")),
            "raw_body_lines":      c.get("raw_body_lines"),
            "outline_nodes":       None,
            "jurisdiction_specific": js,
            "obligation_ids":      c.get("obligation_ids") or [],
        })

    obligations = []
    for o in (data.get("obligations") or []):
        statement_zh = o.get("statement")
        js = make_jurisdiction_specific(
            o.get("is_china_jurisdiction_specific"),
            o.get("china_jurisdiction_features"),
        )
        obligations.append({
            "obligation_id":           o.get("obligation_id"),
            "law_id":                  o.get("law_id"),
            "clause_id":               o.get("clause_id"),
            "jurisdiction":            o.get("jurisdiction", "CN"),
            "article_reference":       o.get("article_reference"),
            "article_reference_local": o.get("article_reference_local"),
            "source_reference":        o.get("source_reference"),
            "category":                o.get("category"),
            "type":                    o.get("type"),
            "actor":                   o.get("actor"),
            "statement":               statement_zh,
            "statement_en":            None,
            "statement_en_source":     "pending",
            "jurisdiction_specific":   js,
        })

    summary_raw = data.get("summary", {})
    key_clauses_raw = summary_raw.get("key_clauses") or []
    key_clauses = []
    for kc in key_clauses_raw:
        key_clauses.append({
            "article_reference":       kc.get("article_reference"),
            "article_reference_local": kc.get("article_reference_local"),
            "title": i18n(
                zh=kc.get("title") or kc.get("article_reference_local"),
                en=None
            ),
            "category": kc.get("category"),
        })

    summary = {
        "law_id":                          summary_raw.get("law_id", "PIPL"),
        "clauses_by_category":             summary_raw.get("clauses_by_category", {}),
        "obligations_by_type":             summary_raw.get("obligations_by_type", {}),
        "obligations_by_actor":            summary_raw.get("obligations_by_actor", {}),
        "chapter_count":                   None,
        "clauses_per_chapter":             None,
        "jurisdiction_specific_clause_count": summary_raw.get("china_specific_clause_count", 0),
        "jurisdiction_feature_counts":     summary_raw.get("china_feature_counts", {}),
        "key_clauses":                     key_clauses,
    }

    return {
        "law":       law,
        "clauses":   clauses,
        "obligations": obligations,
        "relations": normalize_relations(data.get("relations")),
        "summary":   summary,
    }

# ---------------------------------------------------------------------------
# GDPR normalizer  (source language: EN)
# ---------------------------------------------------------------------------

def normalize_gdpr(data: dict) -> dict:
    law_raw = data.get("law", {})

    law = {
        "law_id":           law_raw.get("law_id", "GDPR"),
        "code":             law_raw.get("code", "GDPR"),
        "name":             law_raw.get("name"),
        "official_title":   law_raw.get("official_title"),
        "jurisdiction":     law_raw.get("jurisdiction", "EU"),
        "language":         law_raw.get("language", "EN"),
        "effective_date":   law_raw.get("effective_date", "2018-05-25"),
        "model":            law_raw.get("model"),
        "source_file":      law_raw.get("source_file"),
        "clause_count":     law_raw.get("clause_count", 0),
        "obligation_count": law_raw.get("obligation_count", 0),
    }

    clauses = []
    for c in (data.get("clauses") or []):
        title_en = c.get("title")
        chapter_title_en = c.get("chapter_title")
        section_title_en = c.get("section_title")

        clauses.append({
            "clause_id":               c.get("clause_id"),
            "clause_type":             c.get("clause_type"),
            "law_id":                  c.get("law_id"),
            "law_name":                c.get("law_name"),
            "law_name_local":          None,
            "jurisdiction":            c.get("jurisdiction", "EU"),
            "article_number":          c.get("article_number"),
            "article_reference":       c.get("article_reference"),
            "article_reference_local": None,
            "alt_references": {
                "section_number":    None,
                "section_reference": None,
            },
            "title":               i18n(zh=None, en=title_en),
            "category":            c.get("category"),           # may be None — enrich later
            "importance":          c.get("importance"),         # may be None
            "is_key_clause":       c.get("is_key_clause"),      # may be None
            "chapter_code":        c.get("chapter_code"),
            "chapter_title":       i18n(zh=None, en=chapter_title_en),
            "section_code":        c.get("section_code"),
            "section_title":       i18n(zh=None, en=section_title_en),
            "text":                c.get("text"),
            "text_en":             c.get("text"),               # EN source IS the text
            "text_en_source":      "original",
            "paragraphs":          normalize_paragraphs(c.get("paragraphs")),
            "raw_body_lines":      None,
            "outline_nodes":       None,
            "jurisdiction_specific": make_jurisdiction_specific(
                c.get("is_jurisdiction_specific"),
                c.get("jurisdiction_features"),
            ),
            "obligation_ids":      c.get("obligation_ids") or [],
        })

    obligations = []
    for o in (data.get("obligations") or []):
        statement_en = o.get("statement")
        obligations.append({
            "obligation_id":           o.get("obligation_id"),
            "law_id":                  o.get("law_id"),
            "clause_id":               o.get("clause_id"),
            "jurisdiction":            o.get("jurisdiction", "EU"),
            "article_reference":       o.get("article_reference"),
            "article_reference_local": None,
            "source_reference":        o.get("source_reference"),
            "category":                o.get("category"),       # may be None — enrich later
            "type":                    o.get("type"),
            "actor":                   o.get("actor"),
            "statement":               statement_en,
            "statement_en":            statement_en,            # EN source IS the statement
            "statement_en_source":     "original",
            "jurisdiction_specific": make_jurisdiction_specific(
                o.get("is_jurisdiction_specific"),
                o.get("jurisdiction_features"),
            ),
        })

    summary_raw = data.get("summary", {})
    summary = {
        "law_id":                          summary_raw.get("law_id", "GDPR"),
        "clauses_by_category":             summary_raw.get("clauses_by_category", {}),
        "obligations_by_type":             summary_raw.get("obligations_by_type", {}),
        "obligations_by_actor":            summary_raw.get("obligations_by_actor", {}),
        "chapter_count":                   summary_raw.get("chapter_count"),
        "clauses_per_chapter":             summary_raw.get("clauses_per_chapter"),
        "jurisdiction_specific_clause_count": summary_raw.get("jurisdiction_specific_clause_count", 0),
        "jurisdiction_feature_counts":     summary_raw.get("jurisdiction_feature_counts", {}),
        "key_clauses":                     [],   # GDPR had no key_clauses; scaffold empty
    }

    return {
        "law":       law,
        "clauses":   clauses,
        "obligations": obligations,
        "relations": normalize_relations(data.get("relations")),
        "summary":   summary,
    }

# ---------------------------------------------------------------------------
# CCPA normalizer  (source language: EN)
# ---------------------------------------------------------------------------

def normalize_ccpa(data: dict) -> dict:
    law_raw = data.get("law", {})

    law = {
        "law_id":           law_raw.get("law_id", "CCPA"),
        "code":             law_raw.get("code", "CCPA"),
        "name":             law_raw.get("name"),
        "official_title":   law_raw.get("official_title"),
        "jurisdiction":     law_raw.get("jurisdiction", "US"),
        "language":         law_raw.get("language", "EN"),
        "effective_date":   law_raw.get("effective_date", "2020-01-01"),
        "model":            law_raw.get("model"),
        "source_file":      law_raw.get("source_file"),
        "clause_count":     law_raw.get("clause_count", 0),
        "obligation_count": law_raw.get("obligation_count", 0),
    }

    clauses = []
    for c in (data.get("clauses") or []):
        title_en = c.get("title")

        # CCPA has no chapter/section codes — derive from section_number if present
        sec_num = c.get("section_number") or ""

        clauses.append({
            "clause_id":               c.get("clause_id"),
            "clause_type":             c.get("clause_type"),
            "law_id":                  c.get("law_id"),
            "law_name":                c.get("law_name"),
            "law_name_local":          None,
            "jurisdiction":            c.get("jurisdiction", "US"),
            "article_number":          c.get("article_number"),
            "article_reference":       c.get("article_reference"),
            "article_reference_local": None,
            "alt_references": {
                "section_number":    c.get("section_number"),
                "section_reference": c.get("section_reference"),
            },
            "title":               i18n(zh=None, en=title_en),
            "category":            c.get("category"),
            "importance":          c.get("importance"),
            "is_key_clause":       c.get("is_key_clause"),      # may be None — enrich later
            "chapter_code":        None,
            "chapter_title":       i18n(zh=None, en=None),
            "section_code":        None,
            "section_title":       i18n(zh=None, en=None),
            "text":                c.get("text"),
            "text_en":             c.get("text"),               # EN source IS the text
            "text_en_source":      "original",
            "paragraphs":          None,                        # CCPA has outline_nodes instead
            "raw_body_lines":      None,
            "outline_nodes":       c.get("outline_nodes"),      # CCPA-specific, preserved
            "jurisdiction_specific": make_jurisdiction_specific(
                c.get("is_us_jurisdiction_specific"),
                c.get("us_jurisdiction_features"),
                c.get("us_jurisdiction_feature_notes"),
            ),
            "obligation_ids":      c.get("obligation_ids") or [],
        })

    obligations = []
    for o in (data.get("obligations") or []):
        statement_en = o.get("statement")
        obligations.append({
            "obligation_id":           o.get("obligation_id"),
            "law_id":                  o.get("law_id"),
            "clause_id":               o.get("clause_id"),
            "jurisdiction":            o.get("jurisdiction", "US"),
            "article_reference":       o.get("article_reference"),
            "article_reference_local": None,
            "source_reference":        o.get("source_reference"),
            "category":                o.get("category"),
            "type":                    o.get("type"),
            "actor":                   o.get("actor"),
            "statement":               statement_en,
            "statement_en":            statement_en,
            "statement_en_source":     "original",
            "jurisdiction_specific": make_jurisdiction_specific(
                o.get("is_us_jurisdiction_specific"),
                o.get("us_jurisdiction_features"),
            ),
        })

    summary_raw = data.get("summary", {})
    key_clauses_raw = summary_raw.get("key_clauses") or []
    key_clauses = []
    for kc in key_clauses_raw:
        # CCPA key_clauses may be plain strings (clause_id refs) or dicts
        if isinstance(kc, str):
            key_clauses.append({
                "article_reference":       kc,
                "article_reference_local": None,
                "title":                   i18n(zh=None, en=None),
                "category":                None,
            })
        else:
            key_clauses.append({
                "article_reference":       kc.get("article_reference"),
                "article_reference_local": None,
                "title": i18n(zh=None, en=kc.get("title")),
                "category": kc.get("category"),
            })

    summary = {
        "law_id":                          summary_raw.get("law_id", "CCPA"),
        "clauses_by_category":             summary_raw.get("clauses_by_category", {}),
        "obligations_by_type":             summary_raw.get("obligations_by_type", {}),
        "obligations_by_actor":            summary_raw.get("obligations_by_actor", {}),
        "chapter_count":                   None,
        "clauses_per_chapter":             None,
        "jurisdiction_specific_clause_count": summary_raw.get("us_specific_clause_count", 0),
        "jurisdiction_feature_counts":     summary_raw.get("us_feature_counts", {}),
        "key_clauses":                     key_clauses,
    }

    return {
        "law":       law,
        "clauses":   clauses,
        "obligations": obligations,
        "relations": normalize_relations(data.get("relations")),
        "summary":   summary,
    }

# ---------------------------------------------------------------------------
# Unified graph builder
# ---------------------------------------------------------------------------

def _build_cross_jurisdiction_links() -> list[dict]:
    return [
        {
            "link_id": "CJL_001",
            "concept": "lawful_basis_for_processing",
            "concept_label": i18n(zh="个人信息处理的合法性基础", en="Lawful Basis for Processing"),
            "relation_type": "equivalent",
            "comparison_basis": ["regulatory objective", "legal effect"],
            "nodes": [
                {"law_id": "CN_PIPL_2021", "clause_id": "CN_PIPL_ART_13", "article_reference": "Article 13", "article_reference_local": "第十三条"},
                {"law_id": "EU_GDPR_2016_679", "clause_id": "GDPR_ART_6", "article_reference": "Article 6", "article_reference_local": None},
                {"law_id": "US_CA_CCPA_CPRA_2018", "clause_id": "CCPA_SEC_1798_100", "article_reference": "Section 1798.100", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="PIPL与GDPR均提供处理合法性基础，CCPA/CPRA则以告知、限制和选择退出机制替代统一合法性基础结构。",
                en="PIPL and GDPR both provide explicit lawful-processing bases, while CCPA/CPRA uses notice, limitation, and opt-out controls instead of a single lawful-basis structure."
            ),
            "status": "scaffold",
        },
        {
            "link_id": "CJL_002",
            "concept": "data_subject_right_to_access",
            "concept_label": i18n(zh="个人信息查阅权", en="Right of Access / Right to Know"),
            "relation_type": "equivalent",
            "comparison_basis": ["user-facing right", "request outcome"],
            "nodes": [
                {"law_id": "CN_PIPL_2021", "clause_id": "CN_PIPL_ART_45", "article_reference": "Article 45", "article_reference_local": "第四十五条"},
                {"law_id": "EU_GDPR_2016_679", "clause_id": "GDPR_ART_15", "article_reference": "Article 15", "article_reference_local": None},
                {"law_id": "US_CA_CCPA_CPRA_2018", "clause_id": "CCPA_SEC_1798_100", "article_reference": "Section 1798.100", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="三者均赋予个人访问或知悉其个人信息处理情况的权利，但具体范围和程序要求有所不同。",
                en="All three grant individuals an access or right-to-know mechanism, although scope and procedure differ."
            ),
            "status": "scaffold",
        },
        {
            "link_id": "CJL_003",
            "concept": "right_to_deletion",
            "concept_label": i18n(zh="删除权", en="Right to Deletion / Right to Erasure"),
            "relation_type": "equivalent",
            "comparison_basis": ["user-facing right", "removal effect"],
            "nodes": [
                {"law_id": "CN_PIPL_2021", "clause_id": "CN_PIPL_ART_47", "article_reference": "Article 47", "article_reference_local": "第四十七条"},
                {"law_id": "EU_GDPR_2016_679", "clause_id": "GDPR_ART_17", "article_reference": "Article 17", "article_reference_local": None},
                {"law_id": "US_CA_CCPA_CPRA_2018", "clause_id": "CCPA_SEC_1798_105", "article_reference": "Section 1798.105", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="GDPR称为被遗忘权，CCPA称为删除权，PIPL则在特定条件下要求处理者删除相关信息。",
                en="GDPR terms it the right to erasure, CCPA the right to deletion, and PIPL requires deletion under specified conditions."
            ),
            "status": "scaffold",
        },
        {
            "link_id": "CJL_004",
            "concept": "children_and_minors",
            "concept_label": i18n(zh="未成年人信息保护", en="Children and Minors"),
            "relation_type": "similar",
            "comparison_basis": ["age threshold", "applicable scenario", "consent mechanism"],
            "nodes": [
                {"law_id": "CN_PIPL_2021", "clause_id": "CN_PIPL_ART_31", "article_reference": "Article 31", "article_reference_local": "第三十一条"},
                {"law_id": "EU_GDPR_2016_679", "clause_id": "GDPR_ART_8", "article_reference": "Article 8", "article_reference_local": None},
                {"law_id": "US_CA_CCPA_CPRA_2018", "clause_id": "CCPA_SEC_1798_120", "article_reference": "Section 1798.120", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="三者均体现未成年人特别保护，但年龄门槛、适用场景与同意机制并不相同。",
                en="All three protect minors, but the age threshold, trigger scenario, and consent path differ."
            ),
            "status": "scaffold",
        },
        {
            "link_id": "CJL_005",
            "concept": "cross_border_transfer",
            "concept_label": i18n(zh="跨境数据流动", en="Cross-Border Transfer"),
            "relation_type": "similar",
            "comparison_basis": ["transfer governance axis", "trigger condition", "safeguard structure"],
            "nodes": [
                {"law_id": "CN_PIPL_2021", "clause_id": "CN_PIPL_ART_38", "article_reference": "Article 38", "article_reference_local": "第三十八条"},
                {"law_id": "EU_GDPR_2016_679", "clause_id": "GDPR_ART_44", "article_reference": "Article 44", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="PIPL与GDPR均对跨境提供个人信息设置专门机制，但制度结构和触发条件不同；CCPA/CPRA不存在稳定的一一对应规则。",
                en="PIPL and GDPR both regulate outbound transfers, but their trigger conditions and safeguard structures differ; CCPA/CPRA does not provide a stable one-to-one counterpart."
            ),
            "status": "scaffold",
        },
        {
            "link_id": "CJL_006",
            "concept": "separate_consent",
            "concept_label": i18n(zh="单独同意", en="Separate Consent"),
            "relation_type": "stricter_than",
            "comparison_basis": ["consent threshold", "sensitive-data trigger"],
            "reference_law_id": "CN_PIPL_2021",
            "nodes": [
                {"law_id": "CN_PIPL_2021", "clause_id": "CN_PIPL_ART_29", "article_reference": "Article 29", "article_reference_local": "第二十九条"},
                {"law_id": "EU_GDPR_2016_679", "clause_id": "GDPR_ART_9", "article_reference": "Article 9", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="在敏感信息场景中，PIPL以单独同意作为更明确的高阈值要求；GDPR第9条则采用特殊类别数据处理的复合条件框架。",
                en="For sensitive-data processing, PIPL uses separate consent as a clearer heightened threshold, while GDPR Article 9 uses a broader special-category conditions framework."
            ),
            "status": "scaffold",
        },
        {
            "link_id": "CJL_007",
            "concept": "consumer_opt_out_controls",
            "concept_label": i18n(zh="消费者退出控制机制", en="Consumer Opt-Out Controls"),
            "relation_type": "no_counterpart",
            "comparison_basis": ["UI control surface", "sale or share opt-out", "limit-use mechanism"],
            "reference_law_id": "US_CA_CCPA_CPRA_2018",
            "nodes": [
                {"law_id": "US_CA_CCPA_CPRA_2018", "clause_id": "CCPA_SEC_1798_120", "article_reference": "Section 1798.120", "article_reference_local": None},
                {"law_id": "US_CA_CCPA_CPRA_2018", "clause_id": "CCPA_SEC_1798_121", "article_reference": "Section 1798.121", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="加州法中的出售或共享退出与限制敏感个人信息使用控制具有明显法域特性，在PIPL和GDPR中不存在稳定对应结构。",
                en="California-style opt-out and limit-use controls for sale, sharing, and sensitive personal information are jurisdiction-specific and do not have a stable counterpart in PIPL or GDPR."
            ),
            "status": "scaffold",
        },
    ]


def _finalize_cross_jurisdiction_links(links: list[dict]) -> list[dict]:
    finalized = copy.deepcopy(links)

    for link in finalized:
        link_id = link.get("link_id")
        if link_id == "CJL_005":
            link["relation_type"] = "cross_related"
            link["comparison_basis"] = [
                "regulatory axis",
                "compliance adjacency",
                "joint review relevance",
            ]
            link["notes"] = i18n(
                zh="\u8be5\u7ec4\u89c4\u5219\u5e76\u975e\u5904\u4e8e\u540c\u4e00\u89c4\u5236\u7ef4\u5ea6\uff0c\u4f46\u5728\u6570\u636e\u6d41\u52a8\u3001\u5bf9\u5916\u63d0\u4f9b\u4e0e\u5408\u89c4\u4fdd\u969c\u5206\u6790\u4e2d\u5177\u6709\u5b9e\u8d28\u5173\u8054\u3002",
                en="These rules do not sit on the same doctrinal axis, but they are materially related when reviewing data flows, onward disclosures, and compliance safeguards.",
            )
        elif link_id == "CJL_006":
            link["concept"] = "sensitive_personal_information"
            link["concept_label"] = i18n(
                zh="\u654f\u611f\u4e2a\u4eba\u4fe1\u606f",
                en="Sensitive Personal Information",
            )
            link["relation_type"] = "broader_narrower"
            link["comparison_basis"] = [
                "thematic scope",
                "sub-scenario specificity",
                "regulatory granularity",
            ]
            link["reference_law_id"] = "EU_GDPR_2016_679"
            link["nodes"] = [
                {
                    "law_id": "CN_PIPL_2021",
                    "clause_id": "CN_PIPL_ART_29",
                    "article_reference": "Article 29",
                    "article_reference_local": "\u7b2c\u4e8c\u5341\u4e5d\u6761",
                },
                {
                    "law_id": "EU_GDPR_2016_679",
                    "clause_id": "GDPR_ART_9",
                    "article_reference": "Article 9",
                    "article_reference_local": None,
                },
                {
                    "law_id": "US_CA_CCPA_CPRA_2018",
                    "clause_id": "CCPA_SEC_1798_121",
                    "article_reference": "Section 1798.121",
                    "article_reference_local": None,
                },
            ]
            link["notes"] = i18n(
                zh="\u654f\u611f\u4e2a\u4eba\u4fe1\u606f\u4e3b\u9898\u5728\u4e0d\u540c\u6cd5\u57df\u4e0b\u5747\u53d7\u5230\u5f3a\u5316\u89c4\u5236\uff0c\u4f46 PIPL \u4ee5\u5355\u72ec\u540c\u610f\u7b49\u5177\u4f53\u573a\u666f\u4e3a\u5207\u5165\uff0cGDPR \u4ee5\u7279\u6b8a\u7c7b\u522b\u6570\u636e\u5904\u7406\u6784\u6210\u66f4\u4e0a\u4f4d\u7684\u6846\u67b6\uff0cCCPA/CPRA \u5219\u4ee5\u9650\u5236\u654f\u611f\u4e2a\u4eba\u4fe1\u606f\u4f7f\u7528\u6784\u6210\u672c\u5730\u5316\u7ec6\u5316\u89c4\u5219\u3002",
                en="Sensitive-data rules share a common theme across regimes, but PIPL focuses on a narrower separate-consent scenario, GDPR Article 9 provides a broader special-category framework, and CCPA/CPRA narrows the issue through limit-use controls for sensitive personal information.",
            )
        elif link_id == "CJL_007":
            link["relation_type"] = "jurisdiction_specific"

    return finalized

def build_unified_graph(pipl_norm, gdpr_norm, ccpa_norm) -> dict:
    """
    Combine all three normalized laws into a single knowledge graph,
    with vocabulary and a seeded cross_jurisdiction_links scaffold.
    """
    _legacy_cross_jurisdiction_links = [
        {
            "link_id": "CJL_001",
            "concept": "lawful_basis_for_processing",
            "concept_label": i18n(zh="个人信息处理的合法性基础", en="Lawful Basis for Processing"),
            "relation_type": "equivalent",
            "nodes": [
                {"law_id": "PIPL", "clause_id": "PIPL_ART_13", "article_reference": "Article 13",  "article_reference_local": "第十三条"},
                {"law_id": "GDPR", "clause_id": "GDPR_ART_6",  "article_reference": "Article 6",   "article_reference_local": None},
                {"law_id": "CCPA", "clause_id": None,           "article_reference": "§1798.100",   "article_reference_local": None},
            ],
            "notes": i18n(
                zh="PIPL规定8种合法性基础；GDPR规定6种；CCPA采用选择退出模式而非选择加入",
                en="PIPL provides 8 lawful bases; GDPR provides 6; CCPA uses opt-out rather than opt-in"
            ),
            "status": "scaffold"   # scaffold = to be reviewed by legal expert
        },
        {
            "link_id": "CJL_002",
            "concept": "data_subject_right_to_access",
            "concept_label": i18n(zh="个人信息查阅权", en="Right of Access / Right to Know"),
            "relation_type": "equivalent",
            "nodes": [
                {"law_id": "PIPL", "clause_id": None, "article_reference": "Article 45", "article_reference_local": "第四十五条"},
                {"law_id": "GDPR", "clause_id": None, "article_reference": "Article 15", "article_reference_local": None},
                {"law_id": "CCPA", "clause_id": None, "article_reference": "§1798.100", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="三者均赋予个人访问其个人信息的权利，但范围与程序有所不同",
                en="All three grant individuals the right to access their personal information, with differences in scope and procedure"
            ),
            "status": "scaffold"
        },
        {
            "link_id": "CJL_003",
            "concept": "right_to_deletion",
            "concept_label": i18n(zh="删除权", en="Right to Deletion / Right to Erasure"),
            "relation_type": "equivalent",
            "nodes": [
                {"law_id": "PIPL", "clause_id": None, "article_reference": "Article 47", "article_reference_local": "第四十七条"},
                {"law_id": "GDPR", "clause_id": None, "article_reference": "Article 17", "article_reference_local": None},
                {"law_id": "CCPA", "clause_id": None, "article_reference": "§1798.105", "article_reference_local": None},
            ],
            "notes": i18n(
                zh="GDPR称为'被遗忘权'；CCPA称为'删除权'；PIPL规定处理者应在特定条件下主动删除",
                en="GDPR terms it 'right to erasure'; CCPA 'right to deletion'; PIPL requires proactive deletion under specific conditions"
            ),
            "status": "scaffold"
        },
    ]

    cross_jurisdiction_links = _finalize_cross_jurisdiction_links(_build_cross_jurisdiction_links())

    all_laws = [pipl_norm["law"], gdpr_norm["law"], ccpa_norm["law"]]
    all_clauses = pipl_norm["clauses"] + gdpr_norm["clauses"] + ccpa_norm["clauses"]
    all_obligations = pipl_norm["obligations"] + gdpr_norm["obligations"] + ccpa_norm["obligations"]
    all_relations = pipl_norm["relations"] + gdpr_norm["relations"] + ccpa_norm["relations"]

    return {
        "meta": {
            "schema_version": "1.0.0",
            "jurisdictions": ["CN", "EU", "US"],
            "laws": [l["law_id"] for l in all_laws],
            "total_clauses": len(all_clauses),
            "total_obligations": len(all_obligations),
            "total_relations": len(all_relations),
            "bilingual_fields": ["title", "chapter_title", "section_title", "text_en", "statement_en"],
            "pending_translations": "PIPL text_en and statement_en fields are pending LLM translation",
        },
        "vocabulary": VOCABULARY,
        "laws": all_laws,
        "clauses": all_clauses,
        "obligations": all_obligations,
        "relations": all_relations,
        "cross_jurisdiction_links": cross_jurisdiction_links,
        "summaries": {
            "PIPL": pipl_norm["summary"],
            "GDPR": gdpr_norm["summary"],
            "CCPA": ccpa_norm["summary"],
        }
    }

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(norm: dict, law_id: str) -> list[str]:
    """Basic validation — returns list of warnings."""
    warnings = []
    for c in norm["clauses"]:
        if not c.get("clause_id"):
            warnings.append(f"[{law_id}] clause missing clause_id: {c.get('article_reference')}")
        if not c.get("article_reference"):
            warnings.append(f"[{law_id}] clause missing article_reference: {c.get('clause_id')}")
    for o in norm["obligations"]:
        if not o.get("obligation_id"):
            warnings.append(f"[{law_id}] obligation missing obligation_id: {o.get('source_reference')}")
        if not o.get("clause_id"):
            warnings.append(f"[{law_id}] obligation missing clause_id: {o.get('obligation_id')}")
    return warnings

# ---------------------------------------------------------------------------
# Stats report
# ---------------------------------------------------------------------------

def print_stats(unified: dict):
    print("\n" + "="*60)
    print("  Unified Knowledge Graph — Build Report")
    print("="*60)
    for law in unified["laws"]:
        lid = law["law_id"]
        n_clauses = sum(1 for c in unified["clauses"] if c["law_id"] == lid)
        n_obls    = sum(1 for o in unified["obligations"] if o["law_id"] == lid)
        n_rels    = sum(1 for r in unified["relations"]
                       if r["source"].startswith(lid) or r["target"].startswith(lid))
        pending_text = sum(1 for c in unified["clauses"]
                          if c["law_id"] == lid and c.get("text_en_source") == "pending")
        pending_stmt = sum(1 for o in unified["obligations"]
                          if o["law_id"] == lid and o.get("statement_en_source") == "pending")
        print(f"\n  {lid} ({law['jurisdiction']})")
        print(f"    clauses:     {n_clauses}")
        print(f"    obligations: {n_obls}")
        print(f"    relations:   {n_rels}")
        if pending_text or pending_stmt:
            print(f"    ⚠ pending EN translations — text: {pending_text}, statements: {pending_stmt}")
        else:
            print(f"    ✓ all EN translations present")
    print(f"\n  cross_jurisdiction_links: {len(unified['cross_jurisdiction_links'])} (scaffold)")
    print(f"  total clauses:     {unified['meta']['total_clauses']}")
    print(f"  total obligations: {unified['meta']['total_obligations']}")
    print(f"  total relations:   {unified['meta']['total_relations']}")
    print("="*60 + "\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

NORMALIZERS = {
    "pipl": normalize_pipl,
    "gdpr": normalize_gdpr,
    "ccpa": normalize_ccpa,
}

def main():
    # --- locate input files ---
    search_dirs = [
        PROJECT_ROOT / "output" / "raw",
        PROJECT_ROOT / "data",
        Path.cwd(),
    ]
    if len(sys.argv) > 1:
        search_dirs.insert(0, Path(sys.argv[1]))

    file_patterns = {
        "pipl": ["PIPL_CN.json", "pipl_cn.json", "pipl.json"],
        "gdpr": ["GDPR_EN_TXT.semantic_network.json", "gdpr.json", "gdpr_en.json"],
        "ccpa": ["CCPA_EN_TXT.semantic_network.json", "ccpa.json", "ccpa_en.json"],
    }

    inputs = {}
    for key, patterns in file_patterns.items():
        for d in search_dirs:
            for pat in patterns:
                p = d / pat
                if p.exists():
                    inputs[key] = p
                    break
            if key in inputs:
                break

    if len(inputs) < 3:
        missing = [k for k in ["pipl", "gdpr", "ccpa"] if k not in inputs]
        print(f"⚠  Could not find input files for: {missing}")
        print("   Searched directories:", [str(d) for d in search_dirs])
        print("   Expected filenames:", file_patterns)
        print("\n   Usage: python normalize_kg.py [input_dir]")
        print("   Proceeding with available files only...\n")

    normalized = {}
    all_warnings = []

    for key, path in inputs.items():
        print(f"  Loading {path.name} ...")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        norm = NORMALIZERS[key](raw)
        warnings = validate(norm, key.upper())
        all_warnings.extend(warnings)
        normalized[key] = norm

        out_path = NORMALIZED_OUTPUT_DIR / f"{key.upper()}_normalized.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(norm, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Wrote {out_path.name}")

    if len(normalized) == 3:
        print("\n  Building unified graph ...")
        unified = build_unified_graph(
            normalized["pipl"], normalized["gdpr"], normalized["ccpa"]
        )
        unified_path = NORMALIZED_OUTPUT_DIR / "unified_knowledge_graph.json"
        with open(unified_path, "w", encoding="utf-8") as f:
            json.dump(unified, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Wrote unified_knowledge_graph.json")
        print_stats(unified)
    else:
        print(f"\n  ⚠ Only {len(normalized)}/3 files found — skipping unified graph build.")

    if all_warnings:
        print(f"  Validation warnings ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"    {w}")
    else:
        print("  ✓ Validation passed — no warnings\n")


if __name__ == "__main__":
    main()
