"""
Data-backed multi-jurisdiction knowledge graph.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from loguru import logger
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = PROJECT_ROOT / "output" / "normalized"
UNIFIED_GRAPH_PATH = NORMALIZED_DIR / "unified_knowledge_graph.json"
SQLITE_GRAPH_PATH = NORMALIZED_DIR / "multi_jurisdiction_kg.sqlite"


JURISDICTION_ALIAS = {
    "CN": "CN",
    "CHINA": "CN",
    "\u4e2d\u56fd": "CN",
    "PIPL": "CN",
    "US": "US",
    "US-CA": "US",
    "USA": "US",
    "UNITED STATES": "US",
    "\u7f8e\u56fd": "US",
    "CCPA": "US",
    "EU": "EU",
    "EUROPEAN UNION": "EU",
    "\u6b27\u76df": "EU",
    "GDPR": "EU",
}


JURISDICTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "CN": {
        "name": "中国大陆",
        "region": "中国大陆",
        "description": "以 PIPL 为核心的中国隐私合规框架。",
        "document_tags": ["china", "pipl", "privacy"],
        "generation_style": "优先覆盖显著告知、单独同意、未成年人保护、问责机制和跨境传输保障。",
    },
    "US": {
        "name": "美国",
        "region": "美国（加州）",
        "description": "以 CCPA/CPRA 为核心的美国隐私合规框架。",
        "document_tags": ["us", "california", "ccpa", "cpra", "privacy"],
        "generation_style": "优先覆盖收集时告知、消费者权利、出售或共享控制以及敏感个人信息限制。",
    },
    "EU": {
        "name": "欧盟",
        "region": "欧盟",
        "description": "以 GDPR 为核心的欧盟隐私合规框架。",
        "document_tags": ["eu", "gdpr", "privacy"],
        "generation_style": "优先覆盖合法性基础、透明度、数据主体权利、跨境传输保障和问责机制。",
    },
}


DEFAULT_LAW_FOCUS: Dict[str, List[str]] = {
    "CN_PIPL_2021": [
        "告知与透明度",
        "合法性基础与同意",
        "敏感个人信息",
        "跨境传输",
        "个人权利",
        "安全与问责",
    ],
    "EU_GDPR_2016_679": [
        "合法性基础",
        "透明度",
        "数据主体权利",
        "控制者问责",
        "安全与数据泄露通知",
        "国际传输",
    ],
    "US_CA_CCPA_CPRA_2018": [
        "收集时告知",
        "消费者权利",
        "出售或共享控制",
        "敏感个人信息限制",
        "服务提供商限制",
        "执法与监管机构权力",
    ],
}


DEFAULT_LAW_AUTHORITY: Dict[str, str] = {
    "CN_PIPL_2021": "NPC Standing Committee",
    "EU_GDPR_2016_679": "European Union",
    "US_CA_CCPA_CPRA_2018": "California Legislature",
}


RELATION_TYPE_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "equivalent": {
        "label_en": "Equivalent Counterpart",
        "label_zh": "等价对应",
        "description_en": (
            "Rules are close enough in regulatory objective and legal effect to be used as "
            "a direct multi-jurisdiction alignment anchor."
        ),
        "direct_merge_allowed": True,
    },
    "similar": {
        "label_en": "Functionally Similar",
        "label_zh": "功能近似",
        "description_en": (
            "Rules pursue a similar governance goal but differ in trigger conditions, scope, "
            "or implementation path, so variance notes must be preserved."
        ),
        "direct_merge_allowed": False,
    },
    "stricter_than": {
        "label_en": "Stricter Constraint",
        "label_zh": "更严格约束",
        "description_en": (
            "One jurisdiction is treated as the stricter reference point for the mapped "
            "concept and should anchor conservative drafting or review."
        ),
        "direct_merge_allowed": False,
    },
    "no_counterpart": {
        "label_en": "No Stable Counterpart",
        "label_zh": "无稳定对应",
        "description_en": (
            "The concept is materially jurisdiction-specific and does not have a stable "
            "counterpart in the compared regimes."
        ),
        "direct_merge_allowed": False,
    },
}


RELATION_TYPE_CATALOG: Dict[str, Dict[str, Any]] = {
    "equivalent": {
        "label_en": "Equivalent Counterpart",
        "label_zh": "等价对应",
        "description_en": (
            "Rules are close enough in regulatory objective and legal effect to be used as "
            "a direct multi-jurisdiction alignment anchor."
        ),
        "meaning_zh": "不同法域规则在规范目标、适用逻辑和法律效果上高度接近，可以作为直接对齐锚点。",
        "determination_basis": [
            "regulatory objective is materially aligned",
            "legal effect is materially aligned",
            "scope or procedure differences do not block direct comparison",
        ],
        "direct_merge_allowed": True,
    },
    "similar": {
        "label_en": "Functionally Similar",
        "label_zh": "功能近似",
        "description_en": (
            "Rules pursue a similar governance goal but differ in trigger conditions, scope, "
            "or implementation path, so variance notes must be preserved."
        ),
        "meaning_zh": "规则治理目标相近，但触发条件、适用范围或实现路径存在差异，需要保留差异说明。",
        "determination_basis": [
            "governance objective is similar",
            "trigger condition or scope differs",
            "implementation path differs enough to block direct merge",
        ],
        "direct_merge_allowed": False,
    },
    "stricter_than": {
        "label_en": "Stricter Constraint",
        "label_zh": "更严格约束",
        "description_en": (
            "One jurisdiction is treated as the stricter reference point for the mapped "
            "concept and should anchor conservative drafting or review."
        ),
        "meaning_zh": "某一法域在门槛、同意强度、程序要求或前置条件上明显更严格，可作为保守基线。",
        "determination_basis": [
            "one jurisdiction imposes a higher threshold",
            "one jurisdiction adds extra preconditions or safeguards",
            "the stricter rule should anchor conservative review or drafting",
        ],
        "direct_merge_allowed": False,
    },
    "no_counterpart": {
        "label_en": "No Stable Counterpart",
        "label_zh": "无稳定对应",
        "description_en": (
            "The concept is materially jurisdiction-specific and does not have a stable "
            "counterpart in the compared regimes."
        ),
        "meaning_zh": "该概念具有明显法域特性，在其他法域中缺乏稳定、可比较的对应规则。",
        "determination_basis": [
            "concept is jurisdiction-specific",
            "no stable multi-regime counterpart exists",
            "comparison can note uniqueness but cannot force alignment",
        ],
        "direct_merge_allowed": False,
    },
}


RELATION_TYPE_TABLE_CATALOG: Dict[str, Dict[str, Any]] = {
    "equivalent": {
        "label_en": "Equivalent Counterpart",
        "label_zh": "\u7b49\u4ef7\u5bf9\u5e94",
        "description_en": (
            "Rules are highly aligned in regulatory objective, application logic, and legal "
            "effect, so they can serve as a direct alignment anchor."
        ),
        "meaning_zh": "\u4e0d\u540c\u6cd5\u57df\u89c4\u5219\u5728\u89c4\u8303\u76ee\u6807\u3001\u9002\u7528\u903b\u8f91\u548c\u6cd5\u5f8b\u6548\u679c\u4e0a\u9ad8\u5ea6\u4e00\u81f4\uff0c\u53ef\u4f5c\u4e3a\u76f4\u63a5\u5bf9\u9f50\u951a\u70b9\u3002",
        "determination_basis": [
            "regulatory objective is materially aligned",
            "application logic is materially aligned",
            "legal effect is materially aligned",
        ],
        "determination_basis_zh": [
            "\u89c4\u5236\u76ee\u6807\u57fa\u672c\u4e00\u81f4",
            "\u9002\u7528\u903b\u8f91\u57fa\u672c\u4e00\u81f4",
            "\u6cd5\u5f8b\u6548\u679c\u57fa\u672c\u4e00\u81f4",
        ],
        "direct_merge_allowed": True,
    },
    "similar": {
        "label_en": "Functionally Similar",
        "label_zh": "\u529f\u80fd\u8fd1\u4f3c",
        "description_en": (
            "Rules pursue a similar governance objective but differ in trigger condition, "
            "scope, threshold, or implementation path."
        ),
        "meaning_zh": "\u89c4\u5219\u6cbb\u7406\u76ee\u6807\u76f8\u8fd1\uff0c\u4f46\u89e6\u53d1\u6761\u4ef6\u3001\u9002\u7528\u8303\u56f4\u3001\u9608\u503c\u6216\u5b9e\u73b0\u8def\u5f84\u5b58\u5728\u5dee\u5f02\u3002",
        "determination_basis": [
            "governance objective is similar",
            "trigger condition, threshold, or scope differs",
            "direct merge would hide material variance",
        ],
        "determination_basis_zh": [
            "\u6cbb\u7406\u76ee\u6807\u76f8\u8fd1",
            "\u89e6\u53d1\u6761\u4ef6\u3001\u9608\u503c\u6216\u9002\u7528\u8303\u56f4\u4e0d\u540c",
            "\u76f4\u63a5\u5408\u5e76\u4f1a\u63a9\u76d6\u5173\u952e\u5dee\u5f02",
        ],
        "direct_merge_allowed": False,
    },
    "broader_narrower": {
        "label_en": "Broader-Narrower",
        "label_zh": "\u4e0a\u4f4d-\u4e0b\u4f4d",
        "description_en": (
            "One rule operates as a broader thematic concept while another is a narrower or "
            "more specific implementation under that concept."
        ),
        "meaning_zh": "\u4e00\u65b9\u89c4\u5219\u8868\u73b0\u4e3a\u66f4\u4e0a\u4f4d\u7684\u62bd\u8c61\u4e3b\u9898\uff0c\u53e6\u4e00\u65b9\u5219\u662f\u5176\u4e0b\u4f4d\u6216\u66f4\u5177\u4f53\u7684\u5b9e\u73b0\u89c4\u5219\u3002",
        "determination_basis": [
            "one rule covers a broader thematic scope",
            "another rule captures a narrower or more specific sub-scenario",
            "hierarchical mapping explains the variance better than direct equivalence",
        ],
        "determination_basis_zh": [
            "\u4e00\u65b9\u89c4\u5219\u8986\u76d6\u66f4\u5bbd\u7684\u4e3b\u9898\u8303\u56f4",
            "\u53e6\u4e00\u65b9\u89c4\u5219\u53ea\u9488\u5bf9\u66f4\u5177\u4f53\u7684\u5b50\u573a\u666f",
            "\u7528\u5c42\u7ea7\u6620\u5c04\u6bd4\u76f4\u63a5\u7b49\u4ef7\u66f4\u80fd\u89e3\u91ca\u5dee\u5f02",
        ],
        "direct_merge_allowed": False,
    },
    "cross_related": {
        "label_en": "Cross-Related",
        "label_zh": "\u4ea4\u53c9\u76f8\u5173",
        "description_en": (
            "Rules do not align on the same doctrinal axis, but they are materially related in "
            "compliance analysis and should be compared together."
        ),
        "meaning_zh": "\u89c4\u5219\u4e0d\u5904\u4e8e\u540c\u4e00\u89c4\u5236\u7ef4\u5ea6\uff0c\u4f46\u5728\u5408\u89c4\u5206\u6790\u4e2d\u5177\u6709\u5b9e\u8d28\u5173\u8054\u3002",
        "determination_basis": [
            "rules sit on different doctrinal axes",
            "compliance analysis still requires joint consideration",
            "relationship is associative rather than equivalent or hierarchical",
        ],
        "determination_basis_zh": [
            "\u89c4\u5219\u6240\u5904\u89c4\u5236\u7ef4\u5ea6\u4e0d\u540c",
            "\u5408\u89c4\u5206\u6790\u4ecd\u9700\u8981\u8054\u5408\u8003\u5bdf",
            "\u5176\u5173\u7cfb\u5c5e\u4e8e\u5173\u8054\u800c\u975e\u7b49\u4ef7\u6216\u5c42\u7ea7",
        ],
        "direct_merge_allowed": False,
    },
    "jurisdiction_specific": {
        "label_en": "Jurisdiction-Specific",
        "label_zh": "\u6cd5\u57df\u7279\u6709",
        "description_en": (
            "The rule is materially jurisdiction-specific and does not have a stable counterpart "
            "in the other regimes."
        ),
        "meaning_zh": "\u8be5\u89c4\u5219\u5177\u6709\u660e\u663e\u7684\u6cd5\u57df\u4f9d\u8d56\u6027\uff0c\u5728\u5176\u4ed6\u6cd5\u57df\u4e2d\u7f3a\u4e4f\u7a33\u5b9a\u5bf9\u5e94\u89c4\u5219\u3002",
        "determination_basis": [
            "rule is jurisdiction-specific in doctrine or remedy design",
            "no stable counterpart exists in the compared regimes",
            "the rule should be preserved as a tagged local extension",
        ],
        "determination_basis_zh": [
            "\u89c4\u5219\u5728\u5236\u5ea6\u7ed3\u6784\u6216\u6551\u6d4e\u673a\u5236\u4e0a\u5177\u6709\u6cd5\u57df\u7279\u6027",
            "\u5728\u5176\u4ed6\u6cd5\u57df\u4e2d\u4e0d\u5b58\u5728\u7a33\u5b9a\u5bf9\u5e94\u89c4\u5219",
            "\u5e94\u4f5c\u4e3a\u672c\u5730\u5316\u6269\u5c55\u6807\u8bb0\u4fdd\u7559",
        ],
        "direct_merge_allowed": False,
    },
}


DEFAULT_CONCEPTS: List[Dict[str, Any]] = [
    {
        "concept_id": "general_provisions",
        "label_en": "General Provisions",
        "label_zh": "\u4e00\u822c\u89c4\u5b9a",
        "description_en": "Scope, principles, definitions, and baseline applicability rules.",
        "categories": ["general", "general_provisions", "definitions", "supplementary", "operative_provisions"],
        "keywords": ["scope", "definitions", "principles", "general provisions", "\u5b9a\u4e49", "\u603b\u5219"],
        "synonyms": ["applicability", "territorial scope", "material scope"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 3,
        "compliance_prompt": "说明产品适用的范围、定义和基础隐私治理框架。",
        "source": "taxonomy",
    },
    {
        "concept_id": "transparency_notice",
        "label_en": "Transparency and Notice",
        "label_zh": "\u900f\u660e\u5ea6\u4e0e\u544a\u77e5",
        "description_en": "Notice requirements before or at the point of collection and processing.",
        "categories": ["transparency", "transparency_and_retention", "notice_and_collection"],
        "keywords": ["notice", "transparency", "inform", "disclose", "collection notice", "\u544a\u77e5", "\u900f\u660e"],
        "synonyms": ["notice at collection", "privacy notice"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "说明处理哪些数据、处理目的、共享对象以及告知时点。",
        "source": "taxonomy",
    },
    {
        "concept_id": "lawful_basis_for_processing",
        "label_en": "Lawful Basis for Processing",
        "label_zh": "\u4e2a\u4eba\u4fe1\u606f\u5904\u7406\u7684\u5408\u6cd5\u6027\u57fa\u7840",
        "description_en": "Legal conditions that make processing permissible.",
        "categories": ["lawful_basis", "lawful_basis_and_consent"],
        "keywords": ["lawful basis", "legal basis", "processing conditions", "authorized processing", "\u5408\u6cd5\u6761\u4ef6", "\u5904\u7406\u4f9d\u636e"],
        "synonyms": ["lawfulness of processing", "processing conditions"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "说明每项重要处理活动的法律依据或授权条件。",
        "source": "taxonomy",
    },
    {
        "concept_id": "consent_management",
        "label_en": "Consent Management",
        "label_zh": "\u540c\u610f\u7ba1\u7406",
        "description_en": "Consent collection, withdrawal, refresh, and opt-in mechanics.",
        "categories": ["consent", "lawful_basis_and_consent"],
        "keywords": ["consent", "withdraw", "opt in", "authorization", "\u540c\u610f", "\u64a4\u56de"],
        "synonyms": ["withdrawal", "opt-in"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "说明何时需要同意、如何取得同意以及用户如何撤回同意。",
        "source": "taxonomy",
    },
    {
        "concept_id": "separate_consent",
        "label_en": "Separate Consent",
        "label_zh": "\u5355\u72ec\u540c\u610f",
        "description_en": "Higher-threshold consent for sensitive or special processing scenarios.",
        "categories": ["sensitive_and_minors", "special_processing_rules"],
        "keywords": ["separate consent", "explicit consent", "\u5355\u72ec\u540c\u610f", "\u660e\u793a\u540c\u610f"],
        "synonyms": ["heightened consent"],
        "jurisdictions": ["CN", "EU"],
        "priority": 4,
        "compliance_prompt": "明确标出需要更高标准或单独同意的处理活动。",
        "source": "taxonomy",
    },
    {
        "concept_id": "sensitive_personal_information",
        "label_en": "Sensitive Personal Information",
        "label_zh": "\u654f\u611f\u4e2a\u4eba\u4fe1\u606f",
        "description_en": "Rules for sensitive, special-category, or otherwise heightened data handling.",
        "categories": ["sensitive_data", "sensitive_information_controls", "sensitive_and_minors"],
        "keywords": ["sensitive personal information", "special categories", "biometric", "health", "financial", "\u654f\u611f\u4e2a\u4eba\u4fe1\u606f"],
        "synonyms": ["special-category data", "sensitive PI"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "说明敏感数据类别、处理条件以及额外控制或用户选择。",
        "source": "taxonomy",
    },
    {
        "concept_id": "children_and_minors",
        "label_en": "Children and Minors",
        "label_zh": "\u672a\u6210\u5e74\u4eba\u4fe1\u606f",
        "description_en": "Special protections, thresholds, and parental or guardian authorization.",
        "categories": ["children", "sensitive_and_minors"],
        "keywords": ["child", "children", "minor", "guardian", "parental consent", "\u672a\u6210\u5e74\u4eba", "\u76d1\u62a4\u4eba"],
        "synonyms": ["minor protection", "parental authorization"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "说明年龄门槛、父母或监护人同意要求以及未成年人权利的处理方式。",
        "source": "taxonomy",
    },
    {
        "concept_id": "data_subject_right_to_access",
        "label_en": "Right of Access / Right to Know",
        "label_zh": "\u4e2a\u4eba\u4fe1\u606f\u67e5\u9605\u6743",
        "description_en": "Rights to access or know personal information and processing details.",
        "categories": ["data_subject_rights", "consumer_rights_access", "individual_rights", "rights_request_handling"],
        "keywords": ["access", "right to know", "copy", "review", "\u67e5\u9605", "\u8bbf\u95ee", "\u77e5\u60c5\u6743"],
        "synonyms": ["consumer right to know", "access request"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "为查阅或知情请求提供明确的申请渠道和响应处理方式。",
        "source": "taxonomy",
    },
    {
        "concept_id": "right_to_correction",
        "label_en": "Right to Correction",
        "label_zh": "\u66f4\u6b63\u6743",
        "description_en": "Rights to correct inaccurate personal information.",
        "categories": ["consumer_rights_correction", "data_subject_rights", "individual_rights"],
        "keywords": ["correction", "rectification", "inaccurate", "\u66f4\u6b63", "\u7ea0\u6b63"],
        "synonyms": ["rectification"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 4,
        "compliance_prompt": "说明用户如何申请更正不准确信息以及身份验证方式。",
        "source": "taxonomy",
    },
    {
        "concept_id": "right_to_deletion",
        "label_en": "Right to Deletion / Right to Erasure",
        "label_zh": "\u5220\u9664\u6743",
        "description_en": "Rights to request deletion or erasure and related exceptions.",
        "categories": ["consumer_rights_deletion", "data_subject_rights", "individual_rights", "retention", "storage_limitation"],
        "keywords": ["deletion", "erasure", "delete", "remove", "\u5220\u9664", "\u6e05\u9664"],
        "synonyms": ["right to be forgotten"],
        "jurisdictions": ["CN", "EU", "US"],
        "priority": 5,
        "compliance_prompt": "说明可申请删除的情形、适用例外以及处理结果的告知方式。",
        "source": "taxonomy",
    },
    {
        "concept_id": "data_portability",
        "label_en": "Data Portability",
        "label_zh": "\u6570\u636e\u53ef\u643a\u6743",
        "description_en": "Rights to transfer or receive personal data in a usable format.",
        "categories": ["data_subject_rights", "individual_rights"],
        "keywords": ["portability", "transfer", "portable", "\u8f6c\u79fb", "\u53ef\u643a"],
        "synonyms": ["data transfer right"],
        "jurisdictions": ["CN", "EU"],
        "priority": 4,
        "compliance_prompt": "在适用时说明数据可携或转移权的实现机制。",
        "source": "taxonomy",
    },
]

DEFAULT_CONCEPTS.extend(
    [
        {
            "concept_id": "third_party_sharing_and_sale",
            "label_en": "Third-Party Sharing and Sale",
            "label_zh": "\u7b2c\u4e09\u65b9\u5171\u4eab\u4e0e\u51fa\u552e",
            "description_en": "Disclosure, sharing, sale, or provision of personal information to third parties.",
            "categories": ["sharing", "sale_share_disclosure", "controller_relationships", "special_processing_rules"],
            "keywords": ["share", "sale", "third party", "recipient", "provide to", "\u7b2c\u4e09\u65b9", "\u5171\u4eab", "\u51fa\u552e"],
            "synonyms": ["disclosure to third parties"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 5,
            "compliance_prompt": "披露第三方共享的接收方、目的以及法律或合同边界。",
            "source": "taxonomy",
        },
        {
            "concept_id": "consumer_opt_out_controls",
            "label_en": "Consumer Opt-Out Controls",
            "label_zh": "\u9009\u62e9\u9000\u51fa\u673a\u5236",
            "description_en": "Controls to opt out of sale, sharing, profiling, or other optional processing.",
            "categories": ["opt_out_sale_share", "opt_out_mechanisms", "nondiscrimination_financial_incentives"],
            "keywords": ["opt out", "do not sell", "do not share", "limit use", "\u9000\u51fa", "\u62d2\u7edd"],
            "synonyms": ["preference signal", "do not sell or share"],
            "jurisdictions": ["US", "CN", "EU"],
            "priority": 4,
            "compliance_prompt": "说明可用的选择退出控制、设置位置以及用户行使后的处理结果。",
            "source": "taxonomy",
        },
        {
            "concept_id": "retention_and_storage_limitation",
            "label_en": "Retention and Storage Limitation",
            "label_zh": "\u4fdd\u5b58\u671f\u9650\u4e0e\u5b58\u50a8\u9650\u5236",
            "description_en": "Retention periods, criteria, and deletion schedules.",
            "categories": ["retention", "storage_limitation", "transparency_and_retention"],
            "keywords": ["retention", "storage period", "keep", "delete after", "\u4fdd\u7559\u671f", "\u4fdd\u5b58\u671f"],
            "synonyms": ["storage limitation"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 4,
            "compliance_prompt": "披露保存期限，或至少说明与各项主要目的对应的明确保存标准。",
            "source": "taxonomy",
        },
        {
            "concept_id": "cross_border_transfer",
            "label_en": "Cross-Border Transfer",
            "label_zh": "\u8de8\u5883\u4f20\u8f93",
            "description_en": "International or outbound transfer requirements and safeguards.",
            "categories": ["cross_border", "cross_border_transfer"],
            "keywords": ["cross-border", "international transfer", "overseas", "adequacy", "SCC", "\u8de8\u5883", "\u51fa\u5883", "\u5883\u5916"],
            "synonyms": ["outbound transfer", "international data transfer"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 5,
            "compliance_prompt": "说明传输目的地、保障措施、传输机制以及更严格的出境要求。",
            "source": "taxonomy",
        },
        {
            "concept_id": "security_safeguards",
            "label_en": "Security Safeguards",
            "label_zh": "\u5b89\u5168\u4fdd\u969c\u63aa\u65bd",
            "description_en": "Technical and organizational security controls.",
            "categories": ["security", "accountability_and_security"],
            "keywords": ["security", "encryption", "access control", "security measures", "\u5b89\u5168\u63aa\u65bd", "\u52a0\u5bc6"],
            "synonyms": ["reasonable security", "technical and organizational measures"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 5,
            "compliance_prompt": "在不披露运营机密的前提下，说明具体的安全保障措施。",
            "source": "taxonomy",
        },
        {
            "concept_id": "incident_notification",
            "label_en": "Incident Response and Notification",
            "label_zh": "\u5b89\u5168\u4e8b\u4ef6\u901a\u77e5",
            "description_en": "Incident handling, remediation, and breach notification rules.",
            "categories": ["notification", "accountability_and_security", "breach"],
            "keywords": ["incident", "breach", "notify", "notification", "\u5b89\u5168\u4e8b\u4ef6", "\u901a\u77e5", "\u6cc4\u9732"],
            "synonyms": ["breach notification"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 5,
            "compliance_prompt": "说明安全事件响应流程以及对用户或监管机构的必要通知。",
            "source": "taxonomy",
        },
        {
            "concept_id": "governance_and_accountability",
            "label_en": "Governance and Accountability",
            "label_zh": "\u6cbb\u7406\u4e0e\u95ee\u8d23",
            "description_en": "Internal governance, responsible personnel, assessments, and documentation.",
            "categories": ["accountability", "governance", "accountability_and_security", "vendor_management"],
            "keywords": ["accountability", "assessment", "DPO", "representative", "governance", "\u95ee\u8d23", "\u8bc4\u4f30"],
            "synonyms": ["privacy governance", "impact assessment"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 4,
            "compliance_prompt": "说明高风险处理活动的治理职责、评估和内部控制。",
            "source": "taxonomy",
        },
        {
            "concept_id": "automated_decision_making",
            "label_en": "Automated Decision-Making",
            "label_zh": "\u81ea\u52a8\u5316\u51b3\u7b56",
            "description_en": "Profiling and automated decision-making restrictions and rights.",
            "categories": ["automated_decision", "special_processing_rules"],
            "keywords": ["automated decision", "profiling", "algorithmic", "\u81ea\u52a8\u5316\u51b3\u7b56", "\u753b\u50cf", "\u7b97\u6cd5"],
            "synonyms": ["profiling"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 4,
            "compliance_prompt": "披露自动化决策、主要影响以及可用的人工复核或异议权利。",
            "source": "taxonomy",
        },
        {
            "concept_id": "vendor_management",
            "label_en": "Vendor and Processor Management",
            "label_zh": "\u53d7\u6258\u5904\u7406\u4e0e\u4f9b\u5e94\u5546\u7ba1\u7406",
            "description_en": "Entrusted processing, processor terms, and downstream supervision.",
            "categories": ["controller_relationships", "vendor_management", "service_provider_contractor_model"],
            "keywords": ["processor", "vendor", "service provider", "contractor", "entrusted", "\u53d7\u6258\u5904\u7406", "\u4f9b\u5e94\u5546"],
            "synonyms": ["processor management", "service provider restrictions"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 4,
            "compliance_prompt": "说明受托处理者或供应商的角色、合同控制和监督要求。",
            "source": "taxonomy",
        },
        {
            "concept_id": "public_authority_processing",
            "label_en": "Public Authority Processing",
            "label_zh": "\u56fd\u5bb6\u673a\u5173\u5904\u7406\u4e2a\u4eba\u4fe1\u606f",
            "description_en": "Special rules for public authorities or state organs processing data.",
            "categories": ["state_organs", "state_governance"],
            "keywords": ["state organ", "public authority", "government", "\u56fd\u5bb6\u673a\u5173", "\u653f\u5e9c"],
            "synonyms": ["public body processing"],
            "jurisdictions": ["CN", "EU"],
            "priority": 3,
            "compliance_prompt": "说明国家机关处理的依据、例外以及特殊传输或披露规则。",
            "source": "taxonomy",
        },
        {
            "concept_id": "enforcement_and_penalties",
            "label_en": "Enforcement and Penalties",
            "label_zh": "\u6267\u6cd5\u4e0e\u5904\u7f5a",
            "description_en": "Regulatory powers, liability, remedies, and penalties.",
            "categories": ["enforcement", "regulatory_enforcement", "liabilities_and_remedies", "administrative_enforcement"],
            "keywords": ["enforcement", "penalty", "fine", "liability", "\u5904\u7f5a", "\u7f5a\u6b3e", "\u6267\u6cd5"],
            "synonyms": ["remedies", "liability"],
            "jurisdictions": ["CN", "EU", "US"],
            "priority": 4,
            "compliance_prompt": "评估与产品处理活动相关的执法风险、用户救济和监管机构权力。",
            "source": "taxonomy",
        },
    ]
)


CATEGORY_TO_CONCEPTS: Dict[str, List[str]] = {
    "general": ["general_provisions"],
    "general_provisions": ["general_provisions"],
    "definitions": ["general_provisions"],
    "core_principles": ["general_provisions", "retention_and_storage_limitation"],
    "lawful_basis": ["lawful_basis_for_processing"],
    "lawful_basis_and_consent": ["lawful_basis_for_processing", "consent_management"],
    "consent": ["consent_management"],
    "transparency": ["transparency_notice"],
    "transparency_and_retention": ["transparency_notice", "retention_and_storage_limitation"],
    "data_subject_rights": ["data_subject_right_to_access", "right_to_correction", "right_to_deletion", "data_portability"],
    "individual_rights": ["data_subject_right_to_access", "right_to_correction", "right_to_deletion", "data_portability"],
    "consumer_rights_access": ["data_subject_right_to_access"],
    "consumer_rights_deletion": ["right_to_deletion"],
    "consumer_rights_correction": ["right_to_correction"],
    "security": ["security_safeguards"],
    "notification": ["incident_notification"],
    "cross_border": ["cross_border_transfer"],
    "cross_border_transfer": ["cross_border_transfer"],
    "sensitive_data": ["sensitive_personal_information"],
    "sensitive_and_minors": ["sensitive_personal_information", "children_and_minors", "separate_consent"],
    "children": ["children_and_minors"],
    "sharing": ["third_party_sharing_and_sale"],
    "sale_share_disclosure": ["third_party_sharing_and_sale"],
    "opt_out_sale_share": ["consumer_opt_out_controls", "third_party_sharing_and_sale"],
    "opt_out_mechanisms": ["consumer_opt_out_controls"],
    "sensitive_information_controls": ["sensitive_personal_information", "consumer_opt_out_controls"],
    "rights_request_handling": ["data_subject_right_to_access", "right_to_correction", "right_to_deletion"],
    "controller_relationships": ["vendor_management", "third_party_sharing_and_sale"],
    "special_processing_rules": ["automated_decision_making", "third_party_sharing_and_sale", "separate_consent"],
    "accountability": ["governance_and_accountability"],
    "governance": ["governance_and_accountability"],
    "accountability_and_security": ["security_safeguards", "incident_notification", "governance_and_accountability"],
    "vendor_management": ["vendor_management"],
    "state_organs": ["public_authority_processing"],
    "state_governance": ["public_authority_processing"],
    "automated_decision": ["automated_decision_making"],
    "retention": ["retention_and_storage_limitation", "right_to_deletion"],
    "storage_limitation": ["retention_and_storage_limitation"],
    "enforcement": ["enforcement_and_penalties"],
    "administrative_enforcement": ["enforcement_and_penalties"],
    "regulatory_enforcement": ["enforcement_and_penalties"],
    "liabilities_and_remedies": ["enforcement_and_penalties"],
    "supplementary": ["general_provisions"],
}


STOPWORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "that",
    "this",
    "shall",
    "must",
    "under",
    "into",
    "from",
    "are",
    "any",
    "all",
    "its",
    "their",
    "such",
    "not",
    "without",
    "section",
    "article",
    "personal",
    "information",
    "data",
}


class RegulationLaw(BaseModel):
    law_id: str
    jurisdiction: str
    code: str
    name: str
    official_title: Optional[str] = None
    description: str = ""
    authority: str = ""
    article_prefix: str = "Article"
    focus: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    source_file: Optional[str] = None


class RegulationClause(BaseModel):
    clause_id: str
    jurisdiction: str
    law_id: str
    law_name: str
    article_reference: str
    article_reference_local: Optional[str] = None
    category: str
    title: str
    title_local: Optional[str] = None
    summary: str
    text: str
    text_local: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    obligation_ids: List[str] = Field(default_factory=list)
    concept_ids: List[str] = Field(default_factory=list)
    importance: int = 1
    is_key_clause: bool = False


class RegulationObligation(BaseModel):
    obligation_id: str
    jurisdiction: str
    category: str
    concept_id: str
    title: str
    description: str
    risk_level: str = "major"
    keywords: List[str] = Field(default_factory=list)
    recommended_policy_language: str
    law_ids: List[str] = Field(default_factory=list)
    clause_ids: List[str] = Field(default_factory=list)
    article_references: List[str] = Field(default_factory=list)
    actor_types: List[str] = Field(default_factory=list)
    source_obligation_ids: List[str] = Field(default_factory=list)


class GraphConcept(BaseModel):
    concept_id: str
    label_en: str
    label_zh: Optional[str] = None
    description_en: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    synonyms: List[str] = Field(default_factory=list)
    jurisdictions: List[str] = Field(default_factory=list)
    priority: int = 3
    compliance_prompt: str = ""
    source: str = "taxonomy"
    is_core: bool = True


class CrossJurisdictionNode(BaseModel):
    law_id: str
    clause_id: Optional[str] = None
    article_reference: Optional[str] = None
    article_reference_local: Optional[str] = None


class CrossJurisdictionLink(BaseModel):
    link_id: str
    concept: str
    concept_label: Dict[str, Optional[str]] = Field(default_factory=dict)
    relation_type: str
    relation_label_en: Optional[str] = None
    relation_label_zh: Optional[str] = None
    relation_description_en: Optional[str] = None
    relation_meaning_zh: Optional[str] = None
    direct_merge_allowed: bool = False
    comparison_basis: List[str] = Field(default_factory=list)
    determination_basis: List[str] = Field(default_factory=list)
    determination_basis_zh: List[str] = Field(default_factory=list)
    reference_law_id: Optional[str] = None
    nodes: List[CrossJurisdictionNode] = Field(default_factory=list)
    notes: Dict[str, Optional[str]] = Field(default_factory=dict)
    status: str = "scaffold"


class KnowledgeGraphStats(BaseModel):
    jurisdictions: List[str]
    law_count: int
    clause_count: int
    obligation_count: int
    concept_count: int = 0
    cross_jurisdiction_link_count: int = 0
    relation_type_counts: Dict[str, int] = Field(default_factory=dict)
    supported_relation_types: List[str] = Field(default_factory=list)


class RelationTypeDefinition(BaseModel):
    relation_type: str
    label_en: str
    label_zh: Optional[str] = None
    description_en: str
    meaning_zh: Optional[str] = None
    determination_basis: List[str] = Field(default_factory=list)
    determination_basis_zh: List[str] = Field(default_factory=list)
    direct_merge_allowed: bool = False
    link_count: int = 0
    example_concepts: List[str] = Field(default_factory=list)
    example_link_ids: List[str] = Field(default_factory=list)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _titleize(token: str) -> str:
    return " ".join(part.capitalize() for part in token.split("_") if part)


def _normalize_relation_type_key(relation_type: Optional[str], link_record: Optional[Dict[str, Any]] = None) -> str:
    key = (relation_type or "").strip().lower()
    link_id = (link_record or {}).get("link_id", "")
    if key in RELATION_TYPE_TABLE_CATALOG:
        return key
    if key == "stricter_than":
        return "broader_narrower"
    if key == "no_counterpart":
        return "jurisdiction_specific"
    if key == "similar" and link_id == "CJL_005":
        return "cross_related"
    return key


def _normalize_cross_jurisdiction_link_record(link_record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(link_record)
    link_id = normalized.get("link_id", "")

    if link_id == "CJL_005":
        normalized["relation_type"] = "cross_related"
        normalized["comparison_basis"] = [
            "regulatory axis",
            "compliance adjacency",
            "joint review relevance",
        ]
    elif link_id == "CJL_006":
        normalized["concept"] = "sensitive_personal_information"
        normalized["concept_label"] = {
            "zh": "\u654f\u611f\u4e2a\u4eba\u4fe1\u606f",
            "en": "Sensitive Personal Information",
        }
        normalized["relation_type"] = "broader_narrower"
        normalized["comparison_basis"] = [
            "thematic scope",
            "sub-scenario specificity",
            "regulatory granularity",
        ]
        normalized["reference_law_id"] = "EU_GDPR_2016_679"
        normalized["nodes"] = [
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
        normalized["notes"] = {
            "zh": (
                "\u654f\u611f\u4e2a\u4eba\u4fe1\u606f\u5728\u4e0d\u540c\u6cd5\u57df\u4e0b\u5747\u53d7\u5230"
                "\u5f3a\u5316\u89c4\u5236\uff0c\u4f46 PIPL \u4ee5\u5355\u72ec\u540c\u610f\u7b49\u5177\u4f53"
                "\u573a\u666f\u4e3a\u5207\u5165\uff0cGDPR \u4ee5\u7279\u6b8a\u7c7b\u522b\u6570\u636e\u5904"
                "\u7406\u6784\u6210\u66f4\u4e0a\u4f4d\u7684\u6846\u67b6\uff0cCCPA/CPRA \u5219\u4ee5\u9650"
                "\u5236\u654f\u611f\u4e2a\u4eba\u4fe1\u606f\u4f7f\u7528\u6784\u6210\u672c\u5730\u5316\u7ec6"
                "\u5316\u89c4\u5219\u3002"
            ),
            "en": (
                "Sensitive-data rules share a common theme across regimes, but PIPL focuses on a "
                "narrower separate-consent scenario, GDPR Article 9 provides a broader special-"
                "category framework, and CCPA/CPRA narrows the issue through limit-use controls "
                "for sensitive personal information."
            ),
        }
    elif link_id == "CJL_007":
        normalized["relation_type"] = "jurisdiction_specific"

    return normalized


def _get_relation_type_metadata(relation_type: Optional[str]) -> Dict[str, Any]:
    key = (relation_type or "").strip().lower()
    if key in RELATION_TYPE_TABLE_CATALOG:
        return RELATION_TYPE_TABLE_CATALOG[key]
    return {
        "label_en": _titleize(key or "related"),
        "label_zh": None,
        "description_en": "Custom relation type loaded from the normalized knowledge graph.",
        "meaning_zh": None,
        "determination_basis": [],
        "determination_basis_zh": [],
        "direct_merge_allowed": False,
    }


def _unique(items: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    output: List[str] = []
    for item in items:
        value = _normalize_spaces(item)
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(value)
    return output


def _tokenize(text: str) -> List[str]:
    ascii_tokens = re.findall(r"[a-z0-9_]+", (text or "").lower())
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]+", text or "")
    cjk_tokens: List[str] = []
    for chunk in cjk_chunks:
        if len(chunk) <= 2:
            cjk_tokens.append(chunk)
        else:
            cjk_tokens.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
    filtered = [token for token in ascii_tokens if token not in STOPWORDS and len(token) >= 2]
    return _unique(filtered + cjk_tokens)


def _extract_keywords(*parts: str, limit: int = 12) -> List[str]:
    keywords: List[str] = []
    for part in parts:
        keywords.extend(_tokenize(part))
    return _unique(keywords)[:limit]


def _combine_text(*parts: Optional[str]) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _score_text_match(query: str, searchable: str, title: str, importance: int) -> float:
    normalized_query = _normalize_spaces(query).lower()
    if not normalized_query:
        return float(importance) / 10.0

    score = 0.0
    if normalized_query in title.lower():
        score += 1.1
    if normalized_query in searchable:
        score += 0.7
    for token in _tokenize(normalized_query):
        if token and token in searchable:
            score += 0.15
    return score + float(importance) / 20.0


class RegulationKnowledgeGraph:
    def __init__(self) -> None:
        self.source_graph = _read_json(UNIFIED_GRAPH_PATH)
        self.laws: Dict[str, RegulationLaw] = {}
        self.clauses: Dict[str, RegulationClause] = {}
        self.raw_obligations: Dict[str, Dict[str, Any]] = {}
        self.obligations: Dict[str, RegulationObligation] = {}
        self.concepts: Dict[str, GraphConcept] = {}
        self.cross_jurisdiction_links: List[CrossJurisdictionLink] = []
        self.clause_concepts: DefaultDict[str, Set[str]] = defaultdict(set)
        self.obligation_concepts: DefaultDict[str, Set[str]] = defaultdict(set)
        self.concept_to_clauses: DefaultDict[str, Set[str]] = defaultdict(set)
        self.concept_to_obligations: DefaultDict[str, Set[str]] = defaultdict(set)
        self.jurisdiction_law_ids: DefaultDict[str, List[str]] = defaultdict(list)
        self._load_laws()
        self._load_concepts_and_links()
        self._load_clauses()
        self._load_obligations()
        self._build_compliance_obligations()
        self._sync_clause_concept_ids()
        self._ensure_sqlite_store()
        logger.info(
            "Knowledge graph initialized from normalized data: "
            f"{len(self.laws)} laws, {len(self.clauses)} clauses, {len(self.obligations)} aggregated obligations, "
            f"{len(self.concepts)} concepts"
        )

    def _load_laws(self) -> None:
        for law_record in self.source_graph.get("laws", []):
            jurisdiction = self.normalize_jurisdiction(law_record.get("jurisdiction")) or (law_record.get("jurisdiction") or "")
            profile = JURISDICTION_PROFILES.get(jurisdiction, {})
            law = RegulationLaw(
                law_id=law_record["law_id"],
                jurisdiction=jurisdiction,
                code=law_record.get("code") or law_record["law_id"],
                name=law_record.get("name") or law_record["law_id"],
                official_title=law_record.get("official_title"),
                description=profile.get("description") or (law_record.get("official_title") or ""),
                authority=DEFAULT_LAW_AUTHORITY.get(law_record["law_id"], ""),
                article_prefix="Section" if jurisdiction == "US" else "Article",
                focus=list(DEFAULT_LAW_FOCUS.get(law_record["law_id"], [])),
                keywords=_unique(
                    [
                        law_record.get("code", ""),
                        law_record.get("name", ""),
                        law_record.get("official_title", ""),
                        jurisdiction,
                    ]
                ),
                effective_date=law_record.get("effective_date"),
                source_file=law_record.get("source_file"),
            )
            self.laws[law.law_id] = law
            self.jurisdiction_law_ids[law.jurisdiction].append(law.law_id)

    def _load_concepts_and_links(self) -> None:
        for concept_record in DEFAULT_CONCEPTS:
            concept = GraphConcept(**concept_record)
            self.concepts[concept.concept_id] = concept

        for link_record in self.source_graph.get("cross_jurisdiction_links", []):
            link_record = _normalize_cross_jurisdiction_link_record(link_record)
            relation_type = _normalize_relation_type_key(
                link_record.get("relation_type", "related"),
                link_record=link_record,
            )
            relation_meta = _get_relation_type_metadata(relation_type)
            link = CrossJurisdictionLink(
                link_id=link_record["link_id"],
                concept=link_record["concept"],
                concept_label={
                    "zh": link_record.get("concept_label", {}).get("zh"),
                    "en": link_record.get("concept_label", {}).get("en"),
                },
                relation_type=relation_type,
                relation_label_en=link_record.get("relation_label_en") or relation_meta["label_en"],
                relation_label_zh=link_record.get("relation_label_zh") or relation_meta["label_zh"],
                relation_description_en=link_record.get("relation_description_en") or relation_meta["description_en"],
                relation_meaning_zh=link_record.get("relation_meaning_zh") or relation_meta.get("meaning_zh"),
                direct_merge_allowed=bool(
                    link_record.get("direct_merge_allowed", relation_meta["direct_merge_allowed"])
                ),
                comparison_basis=list(link_record.get("comparison_basis") or []),
                determination_basis=list(
                    link_record.get("determination_basis") or relation_meta.get("determination_basis") or []
                ),
                determination_basis_zh=list(
                    link_record.get("determination_basis_zh") or relation_meta.get("determination_basis_zh") or []
                ),
                reference_law_id=link_record.get("reference_law_id"),
                nodes=[
                    CrossJurisdictionNode(
                        law_id=node.get("law_id", ""),
                        clause_id=node.get("clause_id"),
                        article_reference=node.get("article_reference"),
                        article_reference_local=node.get("article_reference_local"),
                    )
                    for node in link_record.get("nodes", [])
                ],
                notes={
                    "zh": link_record.get("notes", {}).get("zh"),
                    "en": link_record.get("notes", {}).get("en"),
                },
                status=link_record.get("status", "scaffold"),
            )
            self.cross_jurisdiction_links.append(link)
            if link.concept not in self.concepts:
                self.concepts[link.concept] = GraphConcept(
                    concept_id=link.concept,
                    label_en=link.concept_label.get("en") or _titleize(link.concept),
                    label_zh=link.concept_label.get("zh"),
                    description_en=link.notes.get("en"),
                    categories=[],
                    keywords=_extract_keywords(
                        link.concept,
                        link.concept_label.get("en") or "",
                        link.concept_label.get("zh") or "",
                    ),
                    synonyms=[],
                    jurisdictions=_unique(
                        [
                            self.laws[node.law_id].jurisdiction
                            for node in link.nodes
                            if node.law_id in self.laws
                        ]
                    ),
                    priority=5,
                    compliance_prompt=(
                        f"说明与{link.concept_label.get('zh') or link.concept_label.get('en') or _titleize(link.concept)}"
                        "相关的合规要求。"
                    ),
                    source="cross_jurisdiction_link",
                    is_core=True,
                )

    def _load_clauses(self) -> None:
        for clause_record in self.source_graph.get("clauses", []):
            law = self.laws[clause_record["law_id"]]
            title_en = clause_record.get("title", {}).get("en")
            title_zh = clause_record.get("title", {}).get("zh")
            text_en = clause_record.get("text_en")
            text_zh = clause_record.get("text")
            summary = self._build_clause_summary(clause_record, law)
            clause = RegulationClause(
                clause_id=clause_record["clause_id"],
                jurisdiction=self.normalize_jurisdiction(clause_record.get("jurisdiction")) or law.jurisdiction,
                law_id=law.law_id,
                law_name=law.name,
                article_reference=clause_record.get("article_reference") or clause_record["clause_id"],
                article_reference_local=clause_record.get("article_reference_local"),
                category=clause_record.get("category") or "general",
                title=title_en or title_zh or clause_record["clause_id"],
                title_local=title_zh,
                summary=summary,
                text=text_en or text_zh or "",
                text_local=text_zh,
                keywords=_extract_keywords(
                    title_en or "",
                    title_zh or "",
                    clause_record.get("category") or "",
                    text_en or "",
                    text_zh or "",
                ),
                tags=_unique(
                    [
                        law.jurisdiction.lower(),
                        law.code.lower().replace("/", "_"),
                        (clause_record.get("category") or "general").lower(),
                    ]
                    + list(clause_record.get("jurisdiction_specific", {}).get("features") or [])
                ),
                obligation_ids=list(clause_record.get("obligation_ids") or []),
                concept_ids=[],
                importance=int(clause_record.get("importance") or 1),
                is_key_clause=bool(clause_record.get("is_key_clause")),
            )
            self.clauses[clause.clause_id] = clause
            self._link_clause_to_concepts(clause_record, clause)

    def _load_obligations(self) -> None:
        clause_lookup = self.clauses
        for obligation_record in self.source_graph.get("obligations", []):
            clause = clause_lookup.get(obligation_record["clause_id"])
            if clause is None:
                continue
            statement_en = obligation_record.get("statement_en")
            statement_zh = obligation_record.get("statement")
            concept_ids = set(self.clause_concepts.get(clause.clause_id, set()))
            concept_ids.update(self._match_concepts_by_category(obligation_record.get("category")))
            concept_ids.update(
                self._match_concepts_by_keywords(
                    _combine_text(
                        statement_en,
                        statement_zh,
                        clause.title,
                        clause.title_local,
                    )
                )
            )

            enriched = {
                "obligation_id": obligation_record["obligation_id"],
                "law_id": obligation_record["law_id"],
                "clause_id": obligation_record["clause_id"],
                "jurisdiction": self.normalize_jurisdiction(obligation_record.get("jurisdiction")) or clause.jurisdiction,
                "article_reference": obligation_record.get("article_reference") or clause.article_reference,
                "article_reference_local": obligation_record.get("article_reference_local") or clause.article_reference_local,
                "source_reference": obligation_record.get("source_reference"),
                "category": obligation_record.get("category") or clause.category,
                "type": obligation_record.get("type") or "duty",
                "actor": obligation_record.get("actor") or "general",
                "statement": statement_zh or "",
                "statement_en": statement_en or statement_zh or "",
                "statement_en_source": obligation_record.get("statement_en_source") or "original",
                "jurisdiction_specific": obligation_record.get("jurisdiction_specific") or {},
                "keywords": _extract_keywords(
                    statement_en or "",
                    statement_zh or "",
                    clause.title,
                    clause.title_local or "",
                    obligation_record.get("actor") or "",
                    obligation_record.get("type") or "",
                ),
                "concept_ids": sorted(concept_ids),
                "search_text": _combine_text(
                    statement_en or "",
                    statement_zh or "",
                    clause.title,
                    clause.title_local or "",
                    clause.summary,
                ).lower(),
            }
            self.raw_obligations[enriched["obligation_id"]] = enriched
            for concept_id in concept_ids:
                self.obligation_concepts[enriched["obligation_id"]].add(concept_id)
                self.concept_to_obligations[concept_id].add(enriched["obligation_id"])

    def _build_compliance_obligations(self) -> None:
        grouped: DefaultDict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for obligation in self.raw_obligations.values():
            jurisdiction = obligation["jurisdiction"]
            for concept_id in obligation["concept_ids"]:
                concept = self.concepts.get(concept_id)
                if concept is None or not concept.is_core:
                    continue
                if concept.jurisdictions and jurisdiction not in concept.jurisdictions:
                    continue
                grouped[(jurisdiction, concept_id)].append(obligation)

        for (jurisdiction, concept_id), items in grouped.items():
            concept = self.concepts[concept_id]
            clause_ids = _unique([item["clause_id"] for item in items])
            law_ids = _unique([item["law_id"] for item in items])
            article_refs = _unique([item["article_reference"] for item in items if item.get("article_reference")])
            actor_types = _unique([item["actor"] for item in items if item.get("actor")])
            support_clauses = sorted(
                [self.clauses[clause_id] for clause_id in clause_ids if clause_id in self.clauses],
                key=lambda clause: (clause.importance, clause.is_key_clause),
                reverse=True,
            )
            description = self._build_obligation_description(jurisdiction, concept, support_clauses, article_refs)
            risk_level = self._derive_risk_level(concept, support_clauses)
            keywords = _unique(
                concept.keywords
                + concept.synonyms
                + [clause.title for clause in support_clauses[:3]]
                + [token for item in items[:8] for token in item["keywords"]]
            )[:16]
            regulation_obligation = RegulationObligation(
                obligation_id=f"{jurisdiction}_{concept_id}",
                jurisdiction=jurisdiction,
                category=concept.categories[0] if concept.categories else "general",
                concept_id=concept_id,
                title=concept.label_zh or concept.label_en,
                description=description,
                risk_level=risk_level,
                keywords=keywords,
                recommended_policy_language=concept.compliance_prompt or description,
                law_ids=law_ids,
                clause_ids=clause_ids,
                article_references=article_refs,
                actor_types=actor_types,
                source_obligation_ids=[item["obligation_id"] for item in items],
            )
            self.obligations[regulation_obligation.obligation_id] = regulation_obligation

    def _build_clause_summary(self, clause_record: Dict[str, Any], law: RegulationLaw) -> str:
        title = clause_record.get("title", {}).get("zh") or clause_record.get("title", {}).get("en") or ""
        category = clause_record.get("category") or "general"
        article_reference = clause_record.get("article_reference") or clause_record.get("clause_id")
        return (
            f"{law.name} {article_reference} 涉及{title or _titleize(category)}，"
            f"归属类别 {category}。"
        )

    def _derive_risk_level(
        self,
        concept: GraphConcept,
        support_clauses: Sequence[RegulationClause],
    ) -> str:
        max_importance = max([clause.importance for clause in support_clauses], default=1)
        if concept.priority >= 5 or max_importance >= 5:
            return "critical"
        if concept.priority >= 4 or max_importance >= 4:
            return "major"
        return "minor"

    def _build_obligation_description(
        self,
        jurisdiction: str,
        concept: GraphConcept,
        support_clauses: Sequence[RegulationClause],
        article_references: Sequence[str],
    ) -> str:
        profile = JURISDICTION_PROFILES.get(jurisdiction, {})
        laws = _unique([self.laws[clause.law_id].name for clause in support_clauses if clause.law_id in self.laws])
        clause_titles = _unique([clause.title_local or clause.title for clause in support_clauses[:3]])
        concept_label = concept.label_zh or concept.label_en
        return (
            f"{profile.get('name', jurisdiction)}法域要求对{concept_label}进行披露并建立相应控制。"
            f"主要法律依据来自{', '.join(laws[:2]) or '已规范化的法规集'}"
            f"（{', '.join(article_references[:4])}）。"
            f"代表性条款：{', '.join(clause_titles[:3]) or concept_label}。"
        )

    def _match_concepts_by_category(self, category: Optional[str]) -> Set[str]:
        matched: Set[str] = set()
        if not category:
            return matched
        matched.update(CATEGORY_TO_CONCEPTS.get(category, []))
        category_concept_id = self._ensure_category_concept(category)
        matched.add(category_concept_id)
        return matched

    def _ensure_category_concept(self, category: str) -> str:
        concept_id = f"category::{category}"
        if concept_id not in self.concepts:
            self.concepts[concept_id] = GraphConcept(
                concept_id=concept_id,
                label_en=_titleize(category),
                label_zh=f"法规类别：{category}",
                description_en=f"Auto-generated concept derived from normalized category {category}.",
                categories=[category],
                keywords=_extract_keywords(category, _titleize(category)),
                synonyms=[],
                jurisdictions=["CN", "EU", "US"],
                priority=2,
                compliance_prompt=f"说明与法规类别 {category} 相关的合规要求。",
                source="category",
                is_core=False,
            )
        return concept_id

    def _match_concepts_by_keywords(self, text: str) -> Set[str]:
        normalized = (text or "").lower()
        matched: Set[str] = set()
        for concept_id, concept in self.concepts.items():
            terms = list(concept.keywords) + list(concept.synonyms) + [concept.label_en]
            if any(term and str(term).lower() in normalized for term in terms):
                matched.add(concept_id)
        return matched

    def _link_clause_to_concepts(self, clause_record: Dict[str, Any], clause: RegulationClause) -> None:
        concept_ids: Set[str] = set()
        concept_ids.update(self._match_concepts_by_category(clause.category))
        concept_ids.update(
            self._match_concepts_by_keywords(
                _combine_text(
                    clause.title,
                    clause.title_local,
                    clause.text,
                    clause.text_local,
                    clause_record.get("chapter_title", {}).get("en"),
                    clause_record.get("chapter_title", {}).get("zh"),
                    clause_record.get("section_title", {}).get("en"),
                    clause_record.get("section_title", {}).get("zh"),
                )
            )
        )
        for link in self.cross_jurisdiction_links:
            if any(node.clause_id == clause.clause_id for node in link.nodes):
                concept_ids.add(link.concept)

        self.clause_concepts[clause.clause_id].update(concept_ids)
        for concept_id in concept_ids:
            self.concept_to_clauses[concept_id].add(clause.clause_id)

    def _sync_clause_concept_ids(self) -> None:
        for clause_id, clause in self.clauses.items():
            clause.concept_ids = sorted(self.clause_concepts.get(clause_id, set()))

    def _ensure_sqlite_store(self) -> None:
        json_files = list(NORMALIZED_DIR.glob("*.json"))
        source_mtimes = [path.stat().st_mtime for path in json_files] or [UNIFIED_GRAPH_PATH.stat().st_mtime]
        needs_rebuild = not SQLITE_GRAPH_PATH.exists() or SQLITE_GRAPH_PATH.stat().st_mtime < max(source_mtimes)
        if needs_rebuild:
            self._rebuild_sqlite_store()

    def _rebuild_sqlite_store(self) -> None:
        SQLITE_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SQLITE_GRAPH_PATH.exists():
            SQLITE_GRAPH_PATH.unlink()

        connection = sqlite3.connect(str(SQLITE_GRAPH_PATH))
        try:
            connection.executescript(
                """
                CREATE TABLE laws (
                    law_id TEXT PRIMARY KEY,
                    jurisdiction TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    official_title TEXT,
                    description TEXT,
                    authority TEXT,
                    article_prefix TEXT,
                    focus_json TEXT,
                    keywords_json TEXT,
                    effective_date TEXT,
                    source_file TEXT
                );

                CREATE TABLE clauses (
                    clause_id TEXT PRIMARY KEY,
                    law_id TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    article_reference TEXT NOT NULL,
                    article_reference_local TEXT,
                    category TEXT,
                    title TEXT NOT NULL,
                    title_local TEXT,
                    summary TEXT,
                    text TEXT,
                    text_local TEXT,
                    importance INTEGER,
                    is_key_clause INTEGER,
                    concept_ids_json TEXT,
                    obligation_ids_json TEXT,
                    tags_json TEXT,
                    keywords_json TEXT,
                    search_text TEXT
                );

                CREATE TABLE raw_obligations (
                    obligation_id TEXT PRIMARY KEY,
                    law_id TEXT NOT NULL,
                    clause_id TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    article_reference TEXT,
                    article_reference_local TEXT,
                    source_reference TEXT,
                    category TEXT,
                    obligation_type TEXT,
                    actor TEXT,
                    statement TEXT,
                    statement_en TEXT,
                    statement_en_source TEXT,
                    concept_ids_json TEXT,
                    keywords_json TEXT,
                    search_text TEXT,
                    jurisdiction_specific_json TEXT
                );

                CREATE TABLE compliance_obligations (
                    obligation_id TEXT PRIMARY KEY,
                    jurisdiction TEXT NOT NULL,
                    category TEXT,
                    concept_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    risk_level TEXT,
                    keywords_json TEXT,
                    recommended_policy_language TEXT,
                    law_ids_json TEXT,
                    clause_ids_json TEXT,
                    article_references_json TEXT,
                    actor_types_json TEXT,
                    source_obligation_ids_json TEXT
                );

                CREATE TABLE relations (
                    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL
                );

                CREATE TABLE concepts (
                    concept_id TEXT PRIMARY KEY,
                    label_en TEXT NOT NULL,
                    label_zh TEXT,
                    description_en TEXT,
                    categories_json TEXT,
                    keywords_json TEXT,
                    synonyms_json TEXT,
                    jurisdictions_json TEXT,
                    priority INTEGER,
                    compliance_prompt TEXT,
                    source TEXT,
                    is_core INTEGER
                );

                CREATE TABLE clause_concepts (
                    clause_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    PRIMARY KEY (clause_id, concept_id)
                );

                CREATE TABLE obligation_concepts (
                    obligation_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    PRIMARY KEY (obligation_id, concept_id)
                );

                CREATE TABLE cross_jurisdiction_links (
                    link_id TEXT PRIMARY KEY,
                    concept_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    notes_en TEXT,
                    notes_zh TEXT,
                    status TEXT
                );

                CREATE TABLE cross_jurisdiction_nodes (
                    link_id TEXT NOT NULL,
                    law_id TEXT NOT NULL,
                    clause_id TEXT,
                    article_reference TEXT,
                    article_reference_local TEXT
                );

                CREATE TABLE embedding_documents (
                    doc_id TEXT PRIMARY KEY,
                    doc_type TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    law_id TEXT NOT NULL,
                    clause_id TEXT,
                    concept_ids_json TEXT,
                    content TEXT NOT NULL,
                    metadata_json TEXT
                );

                CREATE INDEX idx_clauses_jurisdiction ON clauses (jurisdiction);
                CREATE INDEX idx_clauses_category ON clauses (category);
                CREATE INDEX idx_raw_obligations_jurisdiction ON raw_obligations (jurisdiction);
                CREATE INDEX idx_compliance_obligations_jurisdiction ON compliance_obligations (jurisdiction);
                """
            )

            self._populate_sqlite_store(connection)
            connection.commit()
        finally:
            connection.close()

    def _populate_sqlite_store(self, connection: sqlite3.Connection) -> None:
        connection.executemany(
            """
            INSERT INTO laws (
                law_id, jurisdiction, code, name, official_title, description,
                authority, article_prefix, focus_json, keywords_json, effective_date, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    law.law_id,
                    law.jurisdiction,
                    law.code,
                    law.name,
                    law.official_title,
                    law.description,
                    law.authority,
                    law.article_prefix,
                    json.dumps(law.focus, ensure_ascii=False),
                    json.dumps(law.keywords, ensure_ascii=False),
                    law.effective_date,
                    law.source_file,
                )
                for law in self.laws.values()
            ],
        )

        connection.executemany(
            """
            INSERT INTO clauses (
                clause_id, law_id, jurisdiction, article_reference, article_reference_local, category,
                title, title_local, summary, text, text_local, importance, is_key_clause,
                concept_ids_json, obligation_ids_json, tags_json, keywords_json, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    clause.clause_id,
                    clause.law_id,
                    clause.jurisdiction,
                    clause.article_reference,
                    clause.article_reference_local,
                    clause.category,
                    clause.title,
                    clause.title_local,
                    clause.summary,
                    clause.text,
                    clause.text_local,
                    clause.importance,
                    1 if clause.is_key_clause else 0,
                    json.dumps(clause.concept_ids, ensure_ascii=False),
                    json.dumps(clause.obligation_ids, ensure_ascii=False),
                    json.dumps(clause.tags, ensure_ascii=False),
                    json.dumps(clause.keywords, ensure_ascii=False),
                    _combine_text(clause.title, clause.summary, clause.text).lower(),
                )
                for clause in self.clauses.values()
            ],
        )

        connection.executemany(
            """
            INSERT INTO raw_obligations (
                obligation_id, law_id, clause_id, jurisdiction, article_reference, article_reference_local,
                source_reference, category, obligation_type, actor, statement, statement_en,
                statement_en_source, concept_ids_json, keywords_json, search_text, jurisdiction_specific_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["obligation_id"],
                    item["law_id"],
                    item["clause_id"],
                    item["jurisdiction"],
                    item["article_reference"],
                    item["article_reference_local"],
                    item["source_reference"],
                    item["category"],
                    item["type"],
                    item["actor"],
                    item["statement"],
                    item["statement_en"],
                    item["statement_en_source"],
                    json.dumps(item["concept_ids"], ensure_ascii=False),
                    json.dumps(item["keywords"], ensure_ascii=False),
                    item["search_text"],
                    json.dumps(item["jurisdiction_specific"], ensure_ascii=False),
                )
                for item in self.raw_obligations.values()
            ],
        )

        connection.executemany(
            """
            INSERT INTO compliance_obligations (
                obligation_id, jurisdiction, category, concept_id, title, description, risk_level,
                keywords_json, recommended_policy_language, law_ids_json, clause_ids_json,
                article_references_json, actor_types_json, source_obligation_ids_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    obligation.obligation_id,
                    obligation.jurisdiction,
                    obligation.category,
                    obligation.concept_id,
                    obligation.title,
                    obligation.description,
                    obligation.risk_level,
                    json.dumps(obligation.keywords, ensure_ascii=False),
                    obligation.recommended_policy_language,
                    json.dumps(obligation.law_ids, ensure_ascii=False),
                    json.dumps(obligation.clause_ids, ensure_ascii=False),
                    json.dumps(obligation.article_references, ensure_ascii=False),
                    json.dumps(obligation.actor_types, ensure_ascii=False),
                    json.dumps(obligation.source_obligation_ids, ensure_ascii=False),
                )
                for obligation in self.obligations.values()
            ],
        )

        connection.executemany(
            "INSERT INTO relations (source_id, target_id, relation_type) VALUES (?, ?, ?)",
            [
                (relation.get("source"), relation.get("target"), relation.get("relation"))
                for relation in self.source_graph.get("relations", [])
            ],
        )

        connection.executemany(
            """
            INSERT INTO concepts (
                concept_id, label_en, label_zh, description_en, categories_json, keywords_json,
                synonyms_json, jurisdictions_json, priority, compliance_prompt, source, is_core
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    concept.concept_id,
                    concept.label_en,
                    concept.label_zh,
                    concept.description_en,
                    json.dumps(concept.categories, ensure_ascii=False),
                    json.dumps(concept.keywords, ensure_ascii=False),
                    json.dumps(concept.synonyms, ensure_ascii=False),
                    json.dumps(concept.jurisdictions, ensure_ascii=False),
                    concept.priority,
                    concept.compliance_prompt,
                    concept.source,
                    1 if concept.is_core else 0,
                )
                for concept in self.concepts.values()
            ],
        )

        connection.executemany(
            "INSERT INTO clause_concepts (clause_id, concept_id) VALUES (?, ?)",
            [
                (clause_id, concept_id)
                for clause_id, concept_ids in self.clause_concepts.items()
                for concept_id in concept_ids
            ],
        )
        connection.executemany(
            "INSERT INTO obligation_concepts (obligation_id, concept_id) VALUES (?, ?)",
            [
                (obligation_id, concept_id)
                for obligation_id, concept_ids in self.obligation_concepts.items()
                for concept_id in concept_ids
            ],
        )
        connection.executemany(
            """
            INSERT INTO cross_jurisdiction_links (
                link_id, concept_id, relation_type, notes_en, notes_zh, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    link.link_id,
                    link.concept,
                    link.relation_type,
                    link.notes.get("en"),
                    link.notes.get("zh"),
                    link.status,
                )
                for link in self.cross_jurisdiction_links
            ],
        )
        connection.executemany(
            """
            INSERT INTO cross_jurisdiction_nodes (
                link_id, law_id, clause_id, article_reference, article_reference_local
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    link.link_id,
                    node.law_id,
                    node.clause_id,
                    node.article_reference,
                    node.article_reference_local,
                )
                for link in self.cross_jurisdiction_links
                for node in link.nodes
            ],
        )
        connection.executemany(
            """
            INSERT INTO embedding_documents (
                doc_id, doc_type, jurisdiction, law_id, clause_id, concept_ids_json, content, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["doc_id"],
                    row["doc_type"],
                    row["jurisdiction"],
                    row["law_id"],
                    row.get("clause_id"),
                    json.dumps(row.get("concept_ids") or [], ensure_ascii=False),
                    row["content"],
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                )
                for row in self.get_embedding_documents()
            ],
        )

    def normalize_jurisdiction(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return JURISDICTION_ALIAS.get(normalized, normalized if normalized in JURISDICTION_PROFILES else None)

    def list_supported_jurisdictions(self) -> List[str]:
        return ["CN", "US", "EU"]

    def get_stats(self) -> KnowledgeGraphStats:
        relation_type_counts: DefaultDict[str, int] = defaultdict(int)
        for link in self.cross_jurisdiction_links:
            relation_type_counts[link.relation_type] += 1
        return KnowledgeGraphStats(
            jurisdictions=self.list_supported_jurisdictions(),
            law_count=len(self.laws),
            clause_count=len(self.clauses),
            obligation_count=len(self.obligations),
            concept_count=len(self.concepts),
            cross_jurisdiction_link_count=len(self.cross_jurisdiction_links),
            relation_type_counts={
                relation_type: relation_type_counts.get(relation_type, 0)
                for relation_type in RELATION_TYPE_TABLE_CATALOG
            },
            supported_relation_types=list(RELATION_TYPE_TABLE_CATALOG),
        )

    def get_relation_type_definitions(self) -> List[RelationTypeDefinition]:
        relation_type_to_links: DefaultDict[str, List[CrossJurisdictionLink]] = defaultdict(list)
        for link in self.cross_jurisdiction_links:
            relation_type_to_links[link.relation_type].append(link)

        definitions: List[RelationTypeDefinition] = []
        for relation_type in RELATION_TYPE_TABLE_CATALOG:
            metadata = _get_relation_type_metadata(relation_type)
            links = relation_type_to_links.get(relation_type, [])
            definitions.append(
                RelationTypeDefinition(
                    relation_type=relation_type,
                    label_en=metadata["label_en"],
                    label_zh=metadata.get("label_zh"),
                    description_en=metadata["description_en"],
                    meaning_zh=metadata.get("meaning_zh"),
                    determination_basis=list(metadata.get("determination_basis") or []),
                    determination_basis_zh=list(metadata.get("determination_basis_zh") or []),
                    direct_merge_allowed=bool(metadata.get("direct_merge_allowed", False)),
                    link_count=len(links),
                    example_concepts=[link.concept for link in links[:4]],
                    example_link_ids=[link.link_id for link in links[:4]],
                )
            )
        return definitions

    def get_laws(self, jurisdiction: Optional[str] = None) -> List[RegulationLaw]:
        code = self.normalize_jurisdiction(jurisdiction) if jurisdiction else None
        laws = list(self.laws.values())
        return [law for law in laws if not code or law.jurisdiction == code]

    def get_clauses_for_jurisdiction(self, jurisdiction: str) -> List[RegulationClause]:
        code = self.normalize_jurisdiction(jurisdiction)
        if not code:
            return []
        return [clause for clause in self.clauses.values() if clause.jurisdiction == code]

    def get_obligations_for_jurisdiction(self, jurisdiction: str) -> List[RegulationObligation]:
        code = self.normalize_jurisdiction(jurisdiction)
        if not code:
            return []
        obligations = [obligation for obligation in self.obligations.values() if obligation.jurisdiction == code]
        obligations.sort(
            key=lambda item: (
                {"critical": 3, "major": 2, "minor": 1}.get(item.risk_level, 1),
                item.title,
            ),
            reverse=True,
        )
        return obligations

    def get_raw_obligations_for_jurisdiction(self, jurisdiction: str) -> List[Dict[str, Any]]:
        code = self.normalize_jurisdiction(jurisdiction)
        if not code:
            return []
        return [item for item in self.raw_obligations.values() if item["jurisdiction"] == code]

    def get_related_laws_for_obligation(self, obligation_id: str) -> List[str]:
        obligation = self.obligations.get(obligation_id)
        if obligation:
            return [self.laws[law_id].name for law_id in obligation.law_ids if law_id in self.laws]
        raw = self.raw_obligations.get(obligation_id)
        if raw and raw["law_id"] in self.laws:
            return [self.laws[raw["law_id"]].name]
        return []

    def build_jurisdiction_embedding(self, jurisdiction: str) -> str:
        code = self.normalize_jurisdiction(jurisdiction)
        if not code:
            return ""
        profile = JURISDICTION_PROFILES[code]
        concepts = [obligation.title for obligation in self.get_obligations_for_jurisdiction(code)[:8]]
        return (
            f"法域嵌入[{code}]：重点={', '.join(concepts)}；"
            f"起草策略={profile['generation_style']}；"
            "图谱结构=法律-条款-义务-概念"
        )

    def get_jurisdiction_profile(self, jurisdiction: str) -> Dict[str, Any]:
        code = self.normalize_jurisdiction(jurisdiction)
        if not code:
            raise KeyError(f"Unsupported jurisdiction: {jurisdiction}")
        profile = dict(JURISDICTION_PROFILES[code])
        obligations = self.get_obligations_for_jurisdiction(code)
        profile.update(
            {
                "code": code,
                "laws": [law.name for law in self.get_laws(code)],
                "clause_count": len(self.get_clauses_for_jurisdiction(code)),
                "obligation_count": len(obligations),
                "concept_count": len(self.get_concepts_for_jurisdiction(code)),
                "compliance_points": [item.title for item in obligations[:12]],
                "jurisdiction_embedding": self.build_jurisdiction_embedding(code),
            }
        )
        return profile

    def get_concepts_for_jurisdiction(self, jurisdiction: str) -> List[GraphConcept]:
        code = self.normalize_jurisdiction(jurisdiction)
        if not code:
            return []
        concept_ids = {
            concept_id
            for clause in self.get_clauses_for_jurisdiction(code)
            for concept_id in clause.concept_ids
            if concept_id in self.concepts
        }
        concepts = [self.concepts[concept_id] for concept_id in concept_ids]
        concepts.sort(key=lambda item: (item.priority, item.label_en), reverse=True)
        return concepts

    def get_cross_jurisdiction_links(self, concept_ids: Optional[Sequence[str]] = None) -> List[CrossJurisdictionLink]:
        concept_filter = set(concept_ids or [])
        if not concept_filter:
            return list(self.cross_jurisdiction_links)
        return [link for link in self.cross_jurisdiction_links if link.concept in concept_filter]

    def search_concepts(
        self,
        query: str,
        jurisdictions: Optional[Sequence[str]] = None,
        top_k: int = 5,
    ) -> List[Tuple[GraphConcept, float]]:
        normalized_query = _normalize_spaces(query).lower()
        jurisdiction_filter = {
            self.normalize_jurisdiction(jurisdiction)
            for jurisdiction in (jurisdictions or [])
            if self.normalize_jurisdiction(jurisdiction)
        }
        results: List[Tuple[GraphConcept, float]] = []
        for concept in self.concepts.values():
            if not concept.is_core:
                continue
            if jurisdiction_filter and concept.jurisdictions and not jurisdiction_filter.intersection(concept.jurisdictions):
                continue
            searchable = " ".join(
                [concept.label_en, concept.label_zh or "", concept.description_en or ""]
                + concept.keywords
                + concept.synonyms
            ).lower()
            score = float(concept.priority) / 10.0 if not normalized_query else 0.0
            if normalized_query:
                if normalized_query in concept.label_en.lower():
                    score += 1.2
                if concept.label_zh and normalized_query in concept.label_zh.lower():
                    score += 1.0
                if normalized_query in searchable:
                    score += 0.6
                for token in _tokenize(normalized_query):
                    if token and token in searchable:
                        score += 0.12
            if score > 0:
                results.append((concept, score))
        results.sort(key=lambda item: (item[1], item[0].priority, item[0].label_en), reverse=True)
        return results[: max(1, min(top_k, 20))]

    def search_clauses(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        top_k: int = 5,
        categories: Optional[Sequence[str]] = None,
        concept_ids: Optional[Sequence[str]] = None,
    ) -> List[Tuple[RegulationClause, float]]:
        code = self.normalize_jurisdiction(jurisdiction) if jurisdiction else None
        category_filter = {item.lower() for item in (categories or [])}
        concept_filter = set(concept_ids or [])
        results: List[Tuple[RegulationClause, float]] = []

        for clause in self.clauses.values():
            if code and clause.jurisdiction != code:
                continue
            if category_filter and clause.category.lower() not in category_filter:
                continue
            if concept_filter and not concept_filter.intersection(clause.concept_ids):
                continue

            searchable = _combine_text(
                clause.title,
                clause.title_local,
                clause.summary,
                clause.text,
                clause.text_local,
                " ".join(clause.keywords),
                " ".join(clause.tags),
            ).lower()
            score = _score_text_match(query, searchable, clause.title, clause.importance)
            if concept_filter:
                score += 0.25
            if score > 0:
                results.append((clause, score))

        results.sort(key=lambda item: (item[1], item[0].importance, item[0].is_key_clause), reverse=True)
        return results[: max(1, min(top_k, 50))]

    def query_knowledge_graph(
        self,
        query: str,
        jurisdictions: Optional[Sequence[str]] = None,
        concept_ids: Optional[Sequence[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        normalized_jurisdictions = [
            code
            for code in [self.normalize_jurisdiction(item) for item in (jurisdictions or self.list_supported_jurisdictions())]
            if code
        ]
        if concept_ids:
            matched_concepts = [
                (self.concepts[concept_id], float(self.concepts[concept_id].priority))
                for concept_id in concept_ids
                if concept_id in self.concepts
            ]
        else:
            matched_concepts = self.search_concepts(query, jurisdictions=normalized_jurisdictions, top_k=top_k)

        selected_concept_ids = [concept.concept_id for concept, _ in matched_concepts]
        jurisdiction_results: List[Dict[str, Any]] = []
        for jurisdiction in normalized_jurisdictions:
            clause_matches = self.search_clauses(
                query=query,
                jurisdiction=jurisdiction,
                top_k=max(6, top_k * 2),
                concept_ids=selected_concept_ids or None,
            )
            if not clause_matches and selected_concept_ids:
                clause_matches = self.search_clauses(
                    query="",
                    jurisdiction=jurisdiction,
                    top_k=max(6, top_k * 2),
                    concept_ids=selected_concept_ids,
                )

            concept_results = [
                {
                    "concept_id": concept.concept_id,
                    "label_en": concept.label_en,
                    "label_zh": concept.label_zh,
                    "score": round(score, 4),
                    "priority": concept.priority,
                }
                for concept, score in matched_concepts
                if not concept.jurisdictions or jurisdiction in concept.jurisdictions
            ]

            aggregated_obligations = [
                obligation.model_dump(mode="json")
                for obligation in self.get_obligations_for_jurisdiction(jurisdiction)
                if not selected_concept_ids or obligation.concept_id in selected_concept_ids
            ][: max(4, top_k)]

            raw_obligation_ids = _unique(
                [
                    obligation_id
                    for clause, _ in clause_matches
                    for obligation_id in clause.obligation_ids
                    if obligation_id in self.raw_obligations
                ]
            )[: max(6, top_k * 3)]
            raw_obligations = [self.raw_obligations[obligation_id] for obligation_id in raw_obligation_ids]

            jurisdiction_results.append(
                {
                    "jurisdiction": jurisdiction,
                    "jurisdiction_name": JURISDICTION_PROFILES.get(jurisdiction, {}).get("name", jurisdiction),
                    "laws": [law.model_dump(mode="json") for law in self.get_laws(jurisdiction)],
                    "matched_concepts": concept_results,
                    "clauses": [
                        {
                            **clause.model_dump(mode="json"),
                            "score": round(score, 4),
                        }
                        for clause, score in clause_matches[: max(4, top_k)]
                    ],
                    "aggregated_obligations": aggregated_obligations,
                    "raw_obligations": raw_obligations,
                }
            )

        return {
            "query": query,
            "matched_concepts": [
                {
                    "concept_id": concept.concept_id,
                    "label_en": concept.label_en,
                    "label_zh": concept.label_zh,
                    "score": round(score, 4),
                    "priority": concept.priority,
                    "description_en": concept.description_en,
                }
                for concept, score in matched_concepts
            ],
            "cross_jurisdiction_links": [
                link.model_dump(mode="json")
                for link in self.get_cross_jurisdiction_links(selected_concept_ids or None)
            ],
            "jurisdiction_results": jurisdiction_results,
            "summary_markdown": self.build_query_summary(
                query=query,
                matched_concepts=[concept for concept, _ in matched_concepts],
                jurisdiction_results=jurisdiction_results,
            ),
        }

    def build_query_summary(
        self,
        query: str,
        matched_concepts: Sequence[GraphConcept],
        jurisdiction_results: Sequence[Dict[str, Any]],
    ) -> str:
        jurisdiction_labels = {"CN": "中国", "US": "美国（加州）", "EU": "欧盟"}
        relation_labels = {
            "equivalent": "等价",
            "broader_narrower": "上位与下位",
            "jurisdiction_specific": "法域特有",
            "cross_related": "跨法域相关",
            "related": "相关",
        }
        law_labels = {
            "Personal Information Protection Law": "《中华人民共和国个人信息保护法》",
            "California Consumer Privacy Act / CPRA": "《加州消费者隐私法案》（CCPA/CPRA）",
            "General Data Protection Regulation": "《通用数据保护条例》（GDPR）",
        }
        lines = [
            "# 多法域法规知识图谱摘要",
            "",
            f"- 查询：{query or '核心概念'}",
            f"- 匹配概念：{', '.join(concept.label_zh or concept.label_en for concept in matched_concepts) or '无'}",
            "",
        ]
        links = self.get_cross_jurisdiction_links([concept.concept_id for concept in matched_concepts])
        if links:
            lines.append(
                "- 跨法域关联："
                + ", ".join(
                    f"{link.concept_label.get('zh') or link.concept}"
                    f"［{relation_labels.get(link.relation_type, link.relation_type)}］"
                    for link in links[:6]
                )
            )
            lines.append("")
        for result in jurisdiction_results:
            lines.extend(
                [
                    f"## {jurisdiction_labels.get(result['jurisdiction'], result['jurisdiction_name'])}（{result['jurisdiction']}）",
                    f"- 适用法律：{', '.join(law_labels.get(law['name'], law['name']) for law in result['laws'])}",
                    f"- 相关概念：{', '.join(item.get('label_zh') or item['label_en'] for item in result['matched_concepts']) or '无'}",
                    f"- 检索条款数：{len(result['clauses'])}",
                    f"- 聚合义务数：{len(result['aggregated_obligations'])}",
                ]
            )
            for clause in result["clauses"][:3]:
                lines.append(
                    f"- 法规证据：{law_labels.get(clause['law_name'], clause['law_name'])} "
                    f"{clause['article_reference']} {clause.get('title_local') or clause['title']}"
                )
            lines.append("")
        return "\n".join(lines).strip()

    def get_embedding_documents(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for clause in self.clauses.values():
            rows.append(
                {
                    "doc_id": f"clause::{clause.clause_id}",
                    "doc_type": "clause",
                    "jurisdiction": clause.jurisdiction,
                    "law_id": clause.law_id,
                    "clause_id": clause.clause_id,
                    "concept_ids": clause.concept_ids,
                    "content": _combine_text(clause.title, clause.summary, clause.text),
                    "metadata": {
                        "article_reference": clause.article_reference,
                        "category": clause.category,
                        "importance": clause.importance,
                    },
                }
            )
        for obligation in self.raw_obligations.values():
            rows.append(
                {
                    "doc_id": f"obligation::{obligation['obligation_id']}",
                    "doc_type": "obligation",
                    "jurisdiction": obligation["jurisdiction"],
                    "law_id": obligation["law_id"],
                    "clause_id": obligation["clause_id"],
                    "concept_ids": obligation["concept_ids"],
                    "content": _combine_text(
                        obligation["statement_en"],
                        obligation["statement"],
                        " ".join(obligation["keywords"]),
                    ),
                    "metadata": {
                        "article_reference": obligation["article_reference"],
                        "category": obligation["category"],
                        "type": obligation["type"],
                        "actor": obligation["actor"],
                    },
                }
            )
        return rows

    def iter_clauses(self) -> Iterable[RegulationClause]:
        return self.clauses.values()

    def get_sqlite_path(self) -> Path:
        return SQLITE_GRAPH_PATH


_knowledge_graph: Optional[RegulationKnowledgeGraph] = None


def get_regulation_knowledge_graph() -> RegulationKnowledgeGraph:
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = RegulationKnowledgeGraph()
    return _knowledge_graph
