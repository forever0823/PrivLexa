"""
新增API数据模型
支持升级功能的请求和响应模型
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator


# ============ 政策生成 ============

class GeneratePolicyRequest(BaseModel):
    """政策生成请求"""
    jurisdiction: str = Field(..., description="法域代码 (CN/US/EU)")
    app_name: str = Field(..., min_length=1, description="应用名称")
    app_type: str = Field(..., description="应用类型 (e.g., social, shopping, financial)")
    data_types: List[str] = Field(..., description="收集的数据类型")
    regions: List[str] = Field(default=["default"], description="目标地区")
    use_rag: bool = Field(default=True, description="是否使用RAG增强生成")
    use_fine_tuned_glm: bool = Field(default=False, description="是否使用GLM微调模型")
    additional_context: Optional[str] = Field(default=None, description="额外上下文")

    @field_validator("data_types")
    @classmethod
    def validate_data_types(cls, v: List[str]) -> List[str]:
        """验证data_types至少包含一个元素"""
        if not v or len(v) == 0:
            raise ValueError("data_types 必须至少包含一个元素")
        return v

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, v: str) -> str:
        """验证法域代码"""
        valid_jurisdictions = ["CN", "US", "EU", "JP", "SG", "GLOBAL"]
        if v not in valid_jurisdictions:
            raise ValueError(f"无效的法域: {v}. 有效值: {valid_jurisdictions}")
        return v


class GeneratePolicyResponse(BaseModel):
    """政策生成响应"""
    success: bool = Field(..., description="是否成功")
    policy_id: Optional[str] = Field(None, description="生成的政策ID")
    policy_content: Optional[str] = Field(None, description="生成的政策内容")
    jurisdiction: str = Field(..., description="法域")
    rag_enabled: bool = Field(..., description="是否使用了RAG")
    retrieved_documents: Optional[List[Dict]] = Field(None, description="检索到的文档")
    message: str = Field(..., description="消息")
    error: Optional[str] = Field(None, description="错误信息")


# ============ 冲突检测 ============

class ConflictDetectionRequest(BaseModel):
    """冲突检测请求"""
    policy_text: str = Field(..., description="要检测的政策文本", min_length=1)
    jurisdiction: Optional[str] = Field(None, description="限制到特定法域")
    detection_types: List[str] = Field(
        default=["hard", "soft"],
        description="检测类型 (hard/soft/both)"
    )
    include_suggestions: bool = Field(default=True, description="是否包含建议")

    @field_validator("policy_text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """验证文本"""
        if len(v) > 100000:
            raise ValueError("政策文本过长（最多100000字符）")
        return v


class ConflictDetectionResponse(BaseModel):
    """冲突检测响应"""
    success: bool = Field(..., description="是否成功")
    policy_id: Optional[str] = Field(None, description="政策ID")
    hard_conflicts: List[Dict] = Field(default_factory=list, description="硬约束冲突")
    soft_conflicts: List[Dict] = Field(default_factory=list, description="软匹配冲突")
    total_conflicts: int = Field(..., description="总冲突数")
    critical_count: int = Field(..., description="严重冲突数")
    major_count: int = Field(..., description="重要冲突数")
    minor_count: int = Field(..., description="轻微冲突数")
    message: str = Field(..., description="消息")


# ============ 多法域合规检测 ============

class ComplianceCheckRequest(BaseModel):
    """多法域合规检测请求"""
    policy_text: str = Field(..., description="要检测的政策文本", min_length=1)
    policy_title: str = Field(default="隐私政策", description="政策标题")
    jurisdictions: List[str] = Field(
        default=["CN", "US", "EU"],
        description="要检测的法域列表"
    )
    parallel_execution: bool = Field(default=True, description="是否并行执行检测")
    return_markdown: bool = Field(default=False, description="是否返回Markdown格式报告")

    @field_validator("jurisdictions", mode="before")
    @classmethod
    def validate_jurisdictions(cls, v):
        """验证法域列表"""
        if not v:
            return ["CN", "US", "EU"]
        return v


class ComplianceCheckResponse(BaseModel):
    """多法域合规检测响应"""
    success: bool = Field(..., description="是否成功")
    policy_id: Optional[str] = Field(None, description="政策ID")
    overall_status: str = Field(..., description="总体合规状态")
    overall_score: float = Field(..., description="总体评分")
    jurisdiction_results: List[Dict] = Field(..., description="各法域检测结果")
    critical_violations: List[Dict] = Field(default_factory=list, description="严重违规")
    recommendations: List[str] = Field(default_factory=list, description="改进建议")
    markdown_report: Optional[str] = Field(None, description="Markdown格式报告")
    message: str = Field(..., description="消息")


# ============ 多法域协调Agent ============

class MultiJurisdictionOrchestrationRequest(BaseModel):
    """多法域协调Agent请求"""
    operation: str = Field(..., description="操作类型: generate/detect/comply/full")
    jurisdiction: str = Field(default="CN", description="主法域")
    additional_jurisdictions: List[str] = Field(
        default_factory=list,
        description="额外法域"
    )
    app_name: Optional[str] = Field(None, description="应用名称（用于生成）")
    app_type: Optional[str] = Field(None, description="应用类型（用于生成）")
    data_types: Optional[List[str]] = Field(None, description="数据类型（用于生成）")
    policy_text: Optional[str] = Field(None, description="政策文本（用于检测/合规）")
    include_rag: bool = Field(default=True, description="是否使用RAG")
    parallel_processing: bool = Field(default=True, description="是否并行处理")


class MultiJurisdictionOrchestrationResponse(BaseModel):
    """多法域协调Agent响应"""
    success: bool = Field(..., description="是否成功")
    operation: str = Field(..., description="执行的操作")
    primary_result: Dict[str, Any] = Field(..., description="主要结果")
    jurisdiction_results: Dict[str, Dict] = Field(default_factory=dict, description="各法域结果")
    summary: Dict[str, Any] = Field(..., description="摘要")
    execution_time_ms: float = Field(..., description="执行时间（毫秒）")
    message: str = Field(..., description="消息")


# ============ 法域和文档检索 ============

class ListJurisdictionsResponse(BaseModel):
    """列出可用法域的响应"""
    success: bool = Field(..., description="是否成功")
    jurisdictions: List[Dict] = Field(..., description="法域列表")
    total_count: int = Field(..., description="总数")


class DocumentRetrievalRequest(BaseModel):
    """文档检索请求"""
    query: str = Field(..., description="查询词", min_length=1)
    jurisdiction: Optional[str] = Field(None, description="法域过滤")
    top_k: int = Field(default=5, ge=1, le=20, description="返回的文档数")


class DocumentRetrievalResponse(BaseModel):
    """文档检索响应"""
    success: bool = Field(..., description="是否成功")
    query: str = Field(..., description="查询词")
    jurisdiction: Optional[str] = Field(None, description="法域")
    documents: List[Dict] = Field(..., description="检索到的文档")
    total_count: int = Field(..., description="总数")
    execution_time_ms: float = Field(..., description="执行时间")
