"""
API 数据模型。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


JURISDICTION_ALIAS = {
    "CN": "CN",
    "CHINA": "CN",
    "\u4e2d\u56fd": "CN",
    "PIPL": "CN",
    "US": "US",
    "USA": "US",
    "UNITED STATES": "US",
    "\u7f8e\u56fd": "US",
    "CCPA": "US",
    "EU": "EU",
    "EUROPEAN UNION": "EU",
    "\u6b27\u76df": "EU",
    "GDPR": "EU",
    "GLOBAL": "GLOBAL",
    "JP": "GLOBAL",
    "SG": "GLOBAL",
}

ALLOWED_JURISDICTIONS = {"CN", "US", "EU", "GLOBAL"}
ALLOWED_DETECTION_MODES = {"hard", "soft", "both"}
ALLOWED_OPERATIONS = {"generate", "detect", "comply", "full"}


def _normalize_jurisdiction_code(value: str) -> str:
    normalized = JURISDICTION_ALIAS.get(value.strip().upper(), value.strip().upper())
    if normalized not in ALLOWED_JURISDICTIONS:
        raise ValueError(f"无效的法域: {value}")
    return normalized


def _normalize_jurisdiction_list(values: Optional[List[str]]) -> Optional[List[str]]:
    if values is None:
        return values
    normalized: List[str] = []
    for value in values:
        code = _normalize_jurisdiction_code(value)
        if code not in normalized:
            normalized.append(code)
    return normalized


def _validate_text(value: str, field_name: str, max_length: int = 100000) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    if len(value) > max_length:
        raise ValueError(f"{field_name} 长度过长")
    return value.strip()


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    agent_type: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None
    jurisdiction: Optional[str] = None
    jurisdictions: Optional[List[str]] = None
    parallel_execution: Optional[bool] = None
    return_markdown: Optional[bool] = None
    detection_mode: Optional[str] = None
    enable_conflict_detection: Optional[bool] = False

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, value: str) -> str:
        return _validate_text(value, "agent_type", 64)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _validate_text(value, "message")

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_jurisdiction_code(value)

    @field_validator("jurisdictions")
    @classmethod
    def validate_jurisdictions(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _normalize_jurisdiction_list(value)

    @field_validator("detection_mode")
    @classmethod
    def validate_detection_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DETECTION_MODES:
            raise ValueError(f"detection_mode 必须是 {sorted(ALLOWED_DETECTION_MODES)} 之一")
        return normalized


class AutoChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _validate_text(value, "message")


class ChatResponse(BaseModel):
    success: bool
    agent_type: str
    response: Optional[str] = None
    message: str
    error: Optional[str] = None
    selected_agent: Optional[str] = None
    agent_name: Optional[str] = None


class AgentInfo(BaseModel):
    type: str
    name: str
    description: str
    status: str = "available"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"available", "unavailable", "error"}:
            raise ValueError("无效的状态值")
        return value


class AgentListResponse(BaseModel):
    agents: List[AgentInfo]


class AgentStatusResponse(BaseModel):
    total_agents: int
    active_agents: int
    agents: Dict[str, Dict[str, Any]]


class PrivacyPolicyGenerateRequest(BaseModel):
    app_name: str
    app_type: str
    data_types: List[str]
    regions: List[str] = Field(default_factory=lambda: ["CN"])
    requirements: Optional[str] = None


class ComplianceCheckRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    privacy_policy: Optional[str] = None
    policy_text: Optional[str] = None
    policy_title: Optional[str] = None
    target_regions: Optional[List[str]] = None
    check_points: Optional[List[str]] = None
    jurisdictions: Optional[List[str]] = Field(default_factory=lambda: ["CN"])
    parallel_execution: bool = True
    return_markdown: bool = True
    enable_conflict_detection: bool = False
    detection_mode: Optional[str] = "both"

    @field_validator("jurisdictions")
    @classmethod
    def validate_jurisdictions(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _normalize_jurisdiction_list(value)

    @field_validator("policy_text", "privacy_policy")
    @classmethod
    def validate_optional_policy_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_text(value, "policy_text")

    @field_validator("policy_title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_text(value, "policy_title", 256)

    @field_validator("detection_mode")
    @classmethod
    def validate_detection_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DETECTION_MODES:
            raise ValueError(f"detection_mode 必须是 {sorted(ALLOWED_DETECTION_MODES)} 之一")
        return normalized

    @model_validator(mode="after")
    def ensure_policy_text(self):
        if not self.policy_text and self.privacy_policy:
            self.policy_text = self.privacy_policy
        if not self.policy_text:
            raise ValueError("必须提供 policy_text 或 privacy_policy")
        return self


class ReadabilityCheckRequest(BaseModel):
    privacy_policy: str
    target_audience: Optional[str] = None
    check_dimensions: Optional[List[str]] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    details: Optional[Dict[str, Any]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"healthy", "degraded", "unhealthy"}:
            raise ValueError("无效的健康状态")
        return value


class GeneratePolicyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    jurisdiction: str
    app_name: str
    app_type: str
    data_types: List[str]
    regions: List[str] = Field(default_factory=lambda: ["default"])
    use_rag: bool = True
    use_fine_tuned_glm: bool = False
    additional_context: Optional[str] = None

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, value: str) -> str:
        return _normalize_jurisdiction_code(value)

    @field_validator("app_name", "app_type")
    @classmethod
    def validate_fields(cls, value: str, info) -> str:
        return _validate_text(value, info.field_name, 256)

    @field_validator("additional_context")
    @classmethod
    def validate_context(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_text(value, "additional_context", 5000)


class GeneratePolicyResponse(BaseModel):
    success: bool
    policy_id: Optional[str] = None
    policy: Optional[str] = None
    policy_content: Optional[str] = None
    jurisdiction: Optional[str] = None
    rag_enabled: Optional[bool] = None
    retrieved_documents: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error_message: Optional[str] = None


class ConflictDetectionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    policy_text: str
    jurisdiction: Optional[str] = None
    detection_types: List[str] = Field(default_factory=lambda: ["hard", "soft"])
    detection_mode: Optional[str] = None
    include_suggestions: bool = True

    @field_validator("policy_text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_text(value, "policy_text")

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_jurisdiction_code(value)

    @field_validator("detection_mode")
    @classmethod
    def validate_detection_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DETECTION_MODES:
            raise ValueError(f"detection_mode 必须是 {sorted(ALLOWED_DETECTION_MODES)} 之一")
        return normalized


class ConflictDetectionResponse(BaseModel):
    success: bool
    policy_id: Optional[str] = None
    hard_conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    soft_conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    total_conflicts: Optional[int] = None
    critical_count: Optional[int] = None
    major_count: Optional[int] = None
    minor_count: Optional[int] = None
    detection_results: Optional[str] = None
    detection_mode: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None


class ComplianceCheckResponse(BaseModel):
    success: bool
    policy_id: Optional[str] = None
    policy_title: Optional[str] = None
    jurisdictions: Optional[List[str]] = None
    overall_status: Optional[str] = None
    overall_score: Optional[float] = None
    jurisdiction_results: Optional[List[Dict[str, Any]]] = None
    critical_violations: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    compliance_report: Optional[str] = None
    markdown_report: Optional[str] = None
    report_format: Optional[str] = None
    conflict_detection_enabled: Optional[bool] = None
    conflict_detection_report: Optional[str] = None
    conflict_detection_error: Optional[str] = None
    detection_mode: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None


class MultiJurisdictionOrchestrationRequest(BaseModel):
    operation: str
    jurisdiction: str = "CN"
    additional_jurisdictions: List[str] = Field(default_factory=list)
    app_name: Optional[str] = None
    app_type: Optional[str] = None
    data_types: Optional[List[str]] = None
    policy_text: Optional[str] = None
    include_rag: bool = True
    parallel_processing: bool = True

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_OPERATIONS:
            raise ValueError(f"operation 必须是 {sorted(ALLOWED_OPERATIONS)} 之一")
        return normalized

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, value: str) -> str:
        return _normalize_jurisdiction_code(value)

    @field_validator("additional_jurisdictions")
    @classmethod
    def validate_additional_jurisdictions(cls, value: List[str]) -> List[str]:
        return _normalize_jurisdiction_list(value) or []


class MultiJurisdictionOrchestrationResponse(BaseModel):
    success: bool
    operation: Optional[str] = None
    orchestration_result: Optional[str] = None
    primary_result: Optional[Dict[str, Any]] = None
    jurisdiction_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    jurisdictions: Optional[List[str]] = None
    summary: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None
    message: Optional[str] = None
    error_message: Optional[str] = None


class ListJurisdictionsResponse(BaseModel):
    success: bool
    jurisdictions: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: Optional[int] = None
    error_message: Optional[str] = None


class DocumentRetrievalRequest(BaseModel):
    query: str
    jurisdiction: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return _validate_text(value, "query", 500)

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_jurisdiction_code(value)


class DocumentRetrievalResponse(BaseModel):
    success: bool
    query: Optional[str] = None
    jurisdiction: Optional[str] = None
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    total_found: Optional[int] = None
    total_count: Optional[int] = None
    context_summary: Optional[str] = None
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class KnowledgeGraphQueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Optional[str] = None
    jurisdictions: Optional[List[str]] = Field(default_factory=lambda: ["CN", "US", "EU"])
    concept_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("jurisdictions")
    @classmethod
    def validate_jurisdictions(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _normalize_jurisdiction_list(value)

    @model_validator(mode="after")
    def validate_query_or_concepts(self):
        if not (self.query and self.query.strip()) and not self.concept_ids:
            raise ValueError("query and concept_ids cannot both be empty")
        return self


class KnowledgeGraphQueryResponse(BaseModel):
    success: bool
    query: Optional[str] = None
    matched_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    cross_jurisdiction_links: List[Dict[str, Any]] = Field(default_factory=list)
    jurisdiction_results: List[Dict[str, Any]] = Field(default_factory=list)
    summary_markdown: Optional[str] = None
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class KnowledgeGraphStatsResponse(BaseModel):
    success: bool
    stats: Optional[Dict[str, Any]] = None
    sqlite_path: Optional[str] = None
    error_message: Optional[str] = None


class KnowledgeGraphConceptListResponse(BaseModel):
    success: bool
    concepts: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: Optional[int] = None
    error_message: Optional[str] = None


class KnowledgeGraphRelationTypeListResponse(BaseModel):
    success: bool
    relation_types: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: Optional[int] = None
    error_message: Optional[str] = None
