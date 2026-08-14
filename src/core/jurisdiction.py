"""
基于法规知识图谱构建的法域配置中心。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Sequence, Union

from loguru import logger
from pydantic import BaseModel, Field

try:
    from src.core.knowledge_graph import get_regulation_knowledge_graph
except ImportError:
    from .knowledge_graph import get_regulation_knowledge_graph


class JurisdictionCode(str, Enum):
    CHINA = "CN"
    USA = "US"
    EUROPEAN_UNION = "EU"
    GLOBAL = "GLOBAL"


class ConflictRule(BaseModel):
    rule_id: str
    name: str
    description: str
    category: str
    keywords: List[str] = Field(default_factory=list)
    contradiction_patterns: List[str] = Field(default_factory=list)
    severity: str = "major"


class JurisdictionConfig(BaseModel):
    code: str
    name: str
    region: str
    description: str
    laws: List[str] = Field(default_factory=list)
    system_prompt: str
    compliance_prompt: str
    templates: Dict[str, str] = Field(default_factory=dict)
    conflict_rules: List[ConflictRule] = Field(default_factory=list)
    compliance_points: List[str] = Field(default_factory=list)
    required_obligation_ids: List[str] = Field(default_factory=list)
    rag_enabled: bool = True
    document_tags: List[str] = Field(default_factory=list)
    ontology_tags: List[str] = Field(default_factory=list)
    jurisdiction_embedding: str = ""


DEFAULT_CONFLICT_RULES: List[ConflictRule] = [
    ConflictRule(
        rule_id="retention_conflict",
        name="保存期限冲突",
        description="保存期限相关表述彼此不一致。",
        category="retention",
        keywords=["retention", "delete", "indefinite", "storage period"],
        contradiction_patterns=["indefinitely", "delete after", "permanent", "expiry"],
        severity="major",
    ),
    ConflictRule(
        rule_id="consent_conflict",
        name="同意机制冲突",
        description="同一处理主题下同时出现需要同意和无需同意的表述。",
        category="consent",
        keywords=["consent", "authorization", "withdraw"],
        contradiction_patterns=["explicit consent", "implied consent", "no consent"],
        severity="critical",
    ),
    ConflictRule(
        rule_id="sharing_conflict",
        name="共享披露冲突",
        description="同一政策中同时存在禁止共享与允许广泛共享或出售的表述。",
        category="sharing",
        keywords=["third party", "share", "sell", "service provider"],
        contradiction_patterns=["do not share", "share", "sell"],
        severity="critical",
    ),
    ConflictRule(
        rule_id="rights_conflict",
        name="用户权利冲突",
        description="同一项用户权利同时被授予和否认。",
        category="rights",
        keywords=["access", "deletion", "correction", "portability", "request"],
        contradiction_patterns=["can request", "cannot request", "not available"],
        severity="major",
    ),
    ConflictRule(
        rule_id="cross_border_conflict",
        name="跨境传输冲突",
        description="同一政策中同时存在否认跨境传输和披露跨境传输的表述。",
        category="cross_border",
        keywords=["cross-border", "international transfer", "overseas", "SCC"],
        contradiction_patterns=["domestic only", "international transfer", "overseas"],
        severity="critical",
    ),
]

JURISDICTION_DISPLAY: Dict[str, Dict[str, object]] = {
    JurisdictionCode.CHINA.value: {
        "name": "中国",
        "region": "中国大陆",
        "description": "以《中华人民共和国个人信息保护法》为核心的个人信息保护制度。",
        "laws": ["《中华人民共和国个人信息保护法》（PIPL）"],
    },
    JurisdictionCode.USA.value: {
        "name": "美国（加州）",
        "region": "美国加利福尼亚州",
        "description": "以《加州消费者隐私法案》及其修正案为核心的消费者隐私制度。",
        "laws": ["《加州消费者隐私法案》（CCPA/CPRA）"],
    },
    JurisdictionCode.EUROPEAN_UNION.value: {
        "name": "欧盟",
        "region": "欧洲联盟",
        "description": "以《通用数据保护条例》为核心的数据保护制度。",
        "laws": ["《通用数据保护条例》（GDPR）"],
    },
}

COMPLIANCE_POINT_TRANSLATIONS: Dict[str, str] = {
    "Children and Minors": "儿童与未成年人保护",
    "Consent Management": "同意管理",
    "Cross-Border Transfer": "跨境传输",
    "General Provisions": "一般规定",
    "Incident Response and Notification": "安全事件响应与通知",
    "Lawful Basis for Processing": "处理的合法性基础",
    "Public Authority Processing": "公共机构处理",
    "Retention and Storage Limitation": "保存期限与存储限制",
    "Right of Access / Right to Know": "查阅权与知情权",
    "Right to Correction": "更正权",
    "Right to Deletion / Right to Erasure": "删除权",
    "Security Safeguards": "安全保障措施",
    "Sensitive Personal Information": "敏感个人信息",
    "Separate Consent": "单独同意",
    "Third-Party Sharing and Sale": "第三方共享与出售",
    "Transparency and Notice": "透明度与告知",
    "Vendor and Processor Management": "供应商与受托处理者管理",
}

DISPLAY_LAWS_BY_CODE: Dict[str, List[str]] = {
    code: list(item["laws"])
    for code, item in JURISDICTION_DISPLAY.items()
}
DISPLAY_LAWS_BY_CODE[JurisdictionCode.GLOBAL.value] = [
    "《中华人民共和国个人信息保护法》（PIPL）",
    "《加州消费者隐私法案》（CCPA/CPRA）",
    "《通用数据保护条例》（GDPR）",
]


def localize_compliance_point(value: str) -> str:
    return COMPLIANCE_POINT_TRANSLATIONS.get(value, value)


class JurisdictionManager:
    def __init__(self) -> None:
        self.graph = get_regulation_knowledge_graph()
        self.jurisdictions: Dict[str, JurisdictionConfig] = {}
        self._initialize_jurisdictions()
        logger.info(f"法域管理器初始化完成，共加载 {len(self.jurisdictions)} 个法域")

    def _initialize_jurisdictions(self) -> None:
        for code in self.graph.list_supported_jurisdictions():
            profile = self.graph.get_jurisdiction_profile(code)
            display = JURISDICTION_DISPLAY[code]
            compliance_points = [
                localize_compliance_point(item)
                for item in profile["compliance_points"]
            ]
            self.jurisdictions[code] = JurisdictionConfig(
                code=code,
                name=str(display["name"]),
                region=str(display["region"]),
                description=str(display["description"]),
                laws=list(display["laws"]),
                system_prompt=self._build_generation_prompt(code, compliance_points),
                compliance_prompt=self._build_compliance_prompt(code, compliance_points),
                templates={
                    "basic": f"{display['name']}基础模板",
                    "full": f"{display['name']}增强模板",
                },
                conflict_rules=list(DEFAULT_CONFLICT_RULES),
                compliance_points=compliance_points,
                required_obligation_ids=[
                    obligation.obligation_id
                    for obligation in self.graph.get_obligations_for_jurisdiction(code)
                ],
                rag_enabled=True,
                document_tags=list(profile["document_tags"]),
                ontology_tags=["law", "clause", "obligation", code.lower()],
                jurisdiction_embedding=(
                    f"法域画像[{code}]：核心主题={', '.join(compliance_points[:8])}；"
                    "图谱结构=法律-条款-义务-概念"
                ),
            )

        global_focus: List[str] = []
        global_laws: List[str] = []
        for code in self.graph.list_supported_jurisdictions():
            config = self.jurisdictions[code]
            global_focus.extend(config.compliance_points[:6])
            global_laws.extend(config.laws)

        self.jurisdictions[JurisdictionCode.GLOBAL.value] = JurisdictionConfig(
            code=JurisdictionCode.GLOBAL.value,
            name="全球基线",
            region="全球",
            description="面向中国、美国和欧盟共同基线的统一版本。",
            laws=list(dict.fromkeys(global_laws)),
            system_prompt=(
                "你是全球隐私政策生成专家。生成一份覆盖中国、美国加州和欧盟严格共同基线的协调版本，"
                "并明确标注仍需按法域分别表述的差异。全文使用简体中文。"
            ),
            compliance_prompt=(
                "你是多法域隐私政策合规审查专家。先提取中国、美国加州和欧盟的共同基线，"
                "再识别合规差距与规则冲突。全文使用简体中文。"
            ),
            templates={"basic": "全球基线模板", "full": "全球协调模板"},
            conflict_rules=list(DEFAULT_CONFLICT_RULES),
            compliance_points=list(dict.fromkeys(global_focus)),
            required_obligation_ids=[],
            rag_enabled=True,
            document_tags=["global", "multi-jurisdiction", "privacy"],
            ontology_tags=["law", "clause", "obligation", "global"],
            jurisdiction_embedding="法域画像[GLOBAL]：中国、美国加州与欧盟协调基线",
        )

    def _build_generation_prompt(self, code: str, compliance_points: List[str]) -> str:
        display = JURISDICTION_DISPLAY[code]
        return (
            f"你是面向{display['name']}法域的隐私政策生成专家。除非用户明确要求多法域协调版本，"
            f"否则仅按{display['name']}要求起草。必须遵循{', '.join(display['laws'])}，"
            f"覆盖{', '.join(compliance_points[:8])}，并保证条款可以追溯到对应法律义务。"
            "遇到缺失的业务事实时使用“[待确认：具体事实]”，不得自行编造。全文使用简体中文。"
        )

    def _build_compliance_prompt(self, code: str, compliance_points: List[str]) -> str:
        display = JURISDICTION_DISPLAY[code]
        return (
            f"你是{display['name']}隐私政策合规审查专家。依据{', '.join(display['laws'])}审查政策，"
            f"重点核验{', '.join(compliance_points[:8])}，并给出风险说明和可执行的整改建议。"
            "全文使用简体中文。"
        )

    def normalize_code(self, code: Union[str, JurisdictionCode, None]) -> Optional[str]:
        if code is None:
            return None
        if isinstance(code, JurisdictionCode):
            return code.value
        normalized = self.graph.normalize_jurisdiction(code)
        if normalized:
            return normalized
        if code.strip().upper() == JurisdictionCode.GLOBAL.value:
            return JurisdictionCode.GLOBAL.value
        return None

    def get_jurisdiction(self, code: Union[str, JurisdictionCode]) -> Optional[JurisdictionConfig]:
        normalized = self.normalize_code(code)
        if not normalized:
            logger.warning(f"收到不支持的法域请求: {code}")
            return None
        return self.jurisdictions.get(normalized)

    def get_jurisdiction_by_code(self, code: str) -> Optional[JurisdictionConfig]:
        return self.get_jurisdiction(code)

    def list_jurisdictions(self) -> List[Dict[str, object]]:
        items: List[Dict[str, object]] = []
        for code, config in self.jurisdictions.items():
            if code == JurisdictionCode.GLOBAL.value:
                continue
            items.append(
                {
                    "code": config.code,
                    "name": config.name,
                    "region": config.region,
                    "description": config.description,
                    "laws": DISPLAY_LAWS_BY_CODE.get(config.code, config.laws),
                    "clause_count": len(self.graph.get_clauses_for_jurisdiction(config.code)),
                    "obligation_count": len(self.graph.get_obligations_for_jurisdiction(config.code)),
                }
            )
        return items

    def get_conflict_rules(self, code: Union[str, JurisdictionCode]) -> List[ConflictRule]:
        config = self.get_jurisdiction(code)
        return config.conflict_rules if config else []

    def validate_jurisdiction(self, code: Union[str, JurisdictionCode]) -> bool:
        return self.normalize_code(code) in self.jurisdictions

    def sanitize_jurisdictions(self, codes: Optional[Sequence[str]]) -> List[str]:
        if not codes:
            return [JurisdictionCode.CHINA.value]
        normalized: List[str] = []
        for code in codes:
            valid_code = self.normalize_code(code)
            if valid_code and valid_code not in normalized and valid_code != JurisdictionCode.GLOBAL.value:
                normalized.append(valid_code)
        return normalized or [JurisdictionCode.CHINA.value]


_jurisdiction_manager: Optional[JurisdictionManager] = None


def get_jurisdiction_manager() -> JurisdictionManager:
    global _jurisdiction_manager
    if _jurisdiction_manager is None:
        _jurisdiction_manager = JurisdictionManager()
    return _jurisdiction_manager
