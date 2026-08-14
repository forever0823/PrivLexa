/**
 * API 数据模型 - 与后端 Pydantic 模型匹配
 * 用于类型安全和数据验证
 */

// ============ 基础类型 ============

export type Jurisdiction = "CN" | "US" | "EU" | "JP" | "SG" | "GLOBAL"

export type DetectionMode = "hard" | "soft" | "both" | "comprehensive" | "quick" | "strict"

export type ComplianceFindingStatus = "已覆盖" | "部分覆盖" | "缺失" | "冲突" | "高风险" | "待确认"

// ============ 通用聊天接口 ============

export interface ChatRequest {
  agent_type: string
  message: string
  context?: Record<string, any>
  jurisdiction?: Jurisdiction
  jurisdictions?: Jurisdiction[]
}

export interface ChatResponse {
  success: boolean
  response?: string
  error?: string
  agent_type?: string
  message?: string
}

// ============ v2 API - 隐私政策生成 ============

export interface GeneratePolicyRequest {
  jurisdiction: Jurisdiction
  app_name: string
  app_type: string
  data_types: string[]
  regions?: string[]
  use_rag?: boolean
  use_fine_tuned_glm?: boolean
  additional_context?: string
}

export interface GeneratePolicyResponse {
  success: boolean
  jurisdiction?: Jurisdiction
  policy?: string
  metadata?: {
    jurisdiction?: Jurisdiction
    app_name?: string
    use_rag?: boolean
    use_fine_tuned_glm?: boolean
  }
  error_message?: string
}

// ============ v2 API - 冲突检测 ============

export interface ConflictDetectionRequest {
  policy_text: string
  jurisdiction?: Jurisdiction
  detection_types?: ("hard" | "soft" | "both")[]
  detection_mode?: DetectionMode
  include_suggestions?: boolean
}

export interface ConflictDetectionResponse {
  success: boolean
  hard_conflicts?: Array<{
    status?: ComplianceFindingStatus
    conflict_id: string
    type: "hard_constraint" | "soft_mismatch"
    severity: "critical" | "major" | "minor"
    rule_id?: string
    clause_1: string
    clause_2: string
    location_1: [number, number]
    location_2: [number, number]
    explanation: string
    suggestion: string
  }>
  soft_conflicts?: Array<{
    status?: ComplianceFindingStatus
    clause_1: string
    clause_2: string
    similarity: number
    conflict_type: "soft_mismatch"
    reason: string
  }>
  total_conflicts?: number
  critical_count?: number
  major_count?: number
  minor_count?: number
  detection_results?: string
  detection_mode?: DetectionMode
  error_message?: string
}

// ============ v2 API - 多法域合规检测 ============

export interface ComplianceCheckRequest {
  policy_text?: string
  privacy_policy?: string
  policy_title?: string
  target_regions?: string[]
  check_points?: string[]
  jurisdictions?: Jurisdiction[]
  parallel_execution?: boolean
  return_markdown?: boolean
  enable_conflict_detection?: boolean
  detection_mode?: DetectionMode
}

export interface ComplianceViolation {
  violation_id: string
  clause: string
  law: string
  severity: "critical" | "major" | "minor"
  status: ComplianceFindingStatus
  description: string
  evidence: string
  remediation: string
}

export interface JurisdictionResult {
  jurisdiction: Jurisdiction
  jurisdiction_name: string
  status: ComplianceFindingStatus
  compliance_score: number
  violations_count: number
  violations: ComplianceViolation[]
  recommendations: string[]
  checked_points: Record<string, ComplianceFindingStatus>
  generated_at: string
}

export interface ComplianceCheckResponse {
  success: boolean
  policy_title?: string
  jurisdictions?: Jurisdiction[]
  overall_status?: ComplianceFindingStatus
  overall_score?: number
  jurisdiction_results?: JurisdictionResult[]
  critical_violations?: ComplianceViolation[]
  recommendations?: string[]
  compliance_report?: string
  markdown_report?: string
  report_format?: "markdown" | "json"
  conflict_detection_enabled?: boolean
  conflict_detection_report?: string
  conflict_detection_error?: string
  detection_mode?: DetectionMode
  error_message?: string
}

// ============ v2 API - 多法域编排 ============

export interface MultiJurisdictionOrchestrationRequest {
  operation: "generate" | "detect" | "comply" | "full"
  jurisdiction?: Jurisdiction
  additional_jurisdictions?: Jurisdiction[]
  app_name?: string
  app_type?: string
  data_types?: string[]
  policy_text?: string
  include_rag?: boolean
  parallel_processing?: boolean
}

export interface MultiJurisdictionOrchestrationResponse {
  success: boolean
  operation?: "generate" | "detect" | "comply" | "full"
  orchestration_result?: string
  primary_result?: Record<string, any>
  jurisdiction_results?: Record<Jurisdiction, any>
  jurisdictions?: Jurisdiction[]
  summary?: {
    total_jurisdictions: number
    passed: number
    failed: number
    warnings: number
  }
  execution_time_ms?: number
  error_message?: string
}

// ============ v2 API - 法域列表 ============

export interface JurisdictionInfo {
  code: Jurisdiction
  name: string
  description: string
  laws?: string[]
  regulations?: string[]
  language?: string
}

export interface ListJurisdictionsResponse {
  success: boolean
  jurisdictions?: JurisdictionInfo[]
  total_count?: number
  error_message?: string
}

// ============ v2 API - 文档检索 (RAG) ============

export interface DocumentRetrievalRequest {
  query: string
  jurisdiction?: Jurisdiction
  top_k?: number
}

export interface Document {
  id: string
  title: string
  content: string
  jurisdiction?: Jurisdiction
  relevance_score?: number
  source?: string
}

export interface DocumentRetrievalResponse {
  success: boolean
  query?: string
  jurisdiction?: Jurisdiction
  documents?: Document[]
  total_found?: number
  context_summary?: string
  execution_time_ms?: number
  error_message?: string
}

// ============ 健康检查 ============

export interface HealthCheckDetails {
  [key: string]: {
    status: "healthy" | "degraded" | "unhealthy"
    message?: string
  }
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy"
  timestamp: string
  version?: string
  details?: HealthCheckDetails
}

// ============ Agent 列表 ============

export interface Agent {
  type: string
  name: string
  description: string
  status: "available" | "unavailable" | "error"
}

export interface AgentListResponse {
  agents: Agent[]
}

// ============ 状态端点 ============

export interface StatusResponse {
  success: boolean
  backend_status: "connected" | "disconnected"
  backend_info?: any
  agents?: AgentListResponse
  available_agents?: Agent[]
  timestamp: string
  error?: string
}

// ============ 连接测试 ============

export interface ConnectionTestResponse {
  success: boolean
  message: string
  backend_status?: "healthy" | "degraded" | "unhealthy"
  timestamp: string
  error?: string
}
