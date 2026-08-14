export type GenerateJurisdiction = "CN" | "US" | "EU" | "GLOBAL"
export type ComplianceJurisdiction = "CN" | "US" | "EU"
export type ConflictDetectionMode = "hard" | "soft" | "both"
export type ComplianceOutputFormat = "markdown" | "json"

export interface JurisdictionOption {
  code: GenerateJurisdiction
  name: string
  description: string
  laws?: string[]
}

export interface ComplianceWorkflowOptions {
  enableConflictDetection: boolean
  conflictDetectionMode: ConflictDetectionMode
  enableMultiJurisdiction: boolean
  selectedJurisdictions: Record<ComplianceJurisdiction, boolean>
  parallelExecution: boolean
  outputFormat: ComplianceOutputFormat
}

type ParamReader = {
  get: (name: string) => string | null
}

export const fallbackJurisdictions: JurisdictionOption[] = [
  {
    code: "CN",
    name: "中国大陆",
    description: "适配 PIPL 及配套规则，适合以中国用户为主的产品。",
    laws: ["PIPL"],
  },
  {
    code: "US",
    name: "美国",
    description: "适配 CCPA/CPRA 等要求，适合美国市场投放场景。",
    laws: ["CCPA/CPRA"],
  },
  {
    code: "EU",
    name: "欧盟",
    description: "适配 GDPR 透明度、合法性基础和数据主体权利要求。",
    laws: ["GDPR"],
  },
  {
    code: "GLOBAL",
    name: "全球基线",
    description: "输出更保守的跨法域共同基线版本，适合国际化早期草案。",
    laws: ["CN + US + EU"],
  },
]

export const complianceJurisdictionLabels: Record<ComplianceJurisdiction, string> = {
  CN: "中国大陆 / PIPL",
  US: "美国 / CCPA",
  EU: "欧盟 / GDPR",
}

export const defaultComplianceOptions: ComplianceWorkflowOptions = {
  enableConflictDetection: false,
  conflictDetectionMode: "both",
  enableMultiJurisdiction: true,
  selectedJurisdictions: {
    CN: true,
    US: false,
    EU: false,
  },
  parallelExecution: true,
  outputFormat: "markdown",
}

export function normalizeGenerateJurisdiction(value?: string | null): GenerateJurisdiction {
  if (value === "US" || value === "EU" || value === "GLOBAL") {
    return value
  }
  return "CN"
}

export function getJurisdictionOption(code: GenerateJurisdiction) {
  return fallbackJurisdictions.find((item) => item.code === code) ?? fallbackJurisdictions[0]
}

export function getGenerationDescription(jurisdiction: GenerateJurisdiction) {
  const selected = getJurisdictionOption(jurisdiction)

  if (jurisdiction === "GLOBAL") {
    return "按更保守的跨法域共同基线生成国际版隐私政策，并显式标注仍需拆分处理的法域差异。"
  }

  return `按 ${selected.name} 生成单法域隐私政策草案，不自动混入其他法域义务。`
}

export function buildGenerateConfigHref(jurisdiction: GenerateJurisdiction) {
  const params = new URLSearchParams({ jurisdiction })
  return `/generate?${params.toString()}`
}

export function buildGenerateWorkspaceHref(jurisdiction: GenerateJurisdiction) {
  const params = new URLSearchParams({
    jurisdiction,
    useRag: "1",
  })
  return `/generate/workspace?${params.toString()}`
}

export function getEnabledJurisdictions(options: ComplianceWorkflowOptions): ComplianceJurisdiction[] {
  return (Object.keys(options.selectedJurisdictions) as ComplianceJurisdiction[]).filter(
    (jurisdiction) => options.selectedJurisdictions[jurisdiction],
  )
}

function parseBool(value: string | null, fallback: boolean) {
  if (value === "1" || value === "true") return true
  if (value === "0" || value === "false") return false
  return fallback
}

function normalizeConflictMode(value: string | null): ConflictDetectionMode {
  if (value === "hard" || value === "soft" || value === "both") {
    return value
  }
  return defaultComplianceOptions.conflictDetectionMode
}

function normalizeOutputFormat(value: string | null): ComplianceOutputFormat {
  return value === "json" ? "json" : "markdown"
}

function parseJurisdictions(value: string | null): ComplianceJurisdiction[] {
  if (!value) {
    return getEnabledJurisdictions(defaultComplianceOptions)
  }

  const parsed = value
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter((item): item is ComplianceJurisdiction => item === "CN" || item === "US" || item === "EU")

  return parsed.length > 0 ? Array.from(new Set(parsed)) : getEnabledJurisdictions(defaultComplianceOptions)
}

export function normalizeComplianceOptions(options: ComplianceWorkflowOptions): ComplianceWorkflowOptions {
  const enabled = getEnabledJurisdictions(options)
  const first = enabled[0] ?? "CN"

  const selectedJurisdictions = options.enableMultiJurisdiction
    ? options.selectedJurisdictions
    : {
        CN: first === "CN",
        US: first === "US",
        EU: first === "EU",
      }

  return {
    ...options,
    selectedJurisdictions,
    parallelExecution: options.enableMultiJurisdiction ? options.parallelExecution : false,
  }
}

export function parseComplianceOptions(params: ParamReader): ComplianceWorkflowOptions {
  const selectedCodes = parseJurisdictions(params.get("jurisdictions"))
  const selectedJurisdictions: Record<ComplianceJurisdiction, boolean> = {
    CN: selectedCodes.includes("CN"),
    US: selectedCodes.includes("US"),
    EU: selectedCodes.includes("EU"),
  }

  return normalizeComplianceOptions({
    enableConflictDetection: parseBool(
      params.get("conflicts"),
      defaultComplianceOptions.enableConflictDetection,
    ),
    conflictDetectionMode: normalizeConflictMode(params.get("mode")),
    enableMultiJurisdiction: parseBool(
      params.get("multi"),
      defaultComplianceOptions.enableMultiJurisdiction,
    ),
    selectedJurisdictions,
    parallelExecution: parseBool(
      params.get("parallel"),
      defaultComplianceOptions.parallelExecution,
    ),
    outputFormat: normalizeOutputFormat(params.get("format")),
  })
}

export function buildComplianceQuery(options: ComplianceWorkflowOptions) {
  const normalized = normalizeComplianceOptions(options)
  const params = new URLSearchParams()
  const enabled = getEnabledJurisdictions(normalized)

  if (enabled.length > 0) {
    params.set("jurisdictions", enabled.join(","))
  }
  params.set("multi", normalized.enableMultiJurisdiction ? "1" : "0")
  params.set("conflicts", normalized.enableConflictDetection ? "1" : "0")
  params.set("mode", normalized.conflictDetectionMode)
  params.set("parallel", normalized.parallelExecution ? "1" : "0")
  params.set("format", normalized.outputFormat)
  return params.toString()
}

export function buildComplianceConfigHref(options: ComplianceWorkflowOptions) {
  return `/compliance?${buildComplianceQuery(options)}`
}

export function buildComplianceWorkspaceHref(options: ComplianceWorkflowOptions) {
  return `/compliance/workspace?${buildComplianceQuery(options)}`
}

export function getComplianceExecutionConfig(options: ComplianceWorkflowOptions) {
  const normalized = normalizeComplianceOptions(options)
  const enabled = getEnabledJurisdictions(normalized)
  const effectiveJurisdictions = normalized.enableMultiJurisdiction ? enabled : enabled.slice(0, 1)

  const activeApiEndpoint = normalized.enableConflictDetection
    ? normalized.enableMultiJurisdiction
      ? "/api/v2/compliance-check"
      : "/api/v2/detect-conflicts"
    : normalized.enableMultiJurisdiction
      ? "/api/v2/compliance-check"
      : "/api/compliance"

  const activeAgentType = normalized.enableConflictDetection
    ? normalized.enableMultiJurisdiction
      ? "compliance_checker_multi"
      : "conflict_detector"
    : normalized.enableMultiJurisdiction
      ? "compliance_checker_multi"
      : "compliance_checker"

  return {
    options: normalized,
    enabledJurisdictions: effectiveJurisdictions,
    activeApiEndpoint,
    activeAgentType,
    parallelExecution:
      normalized.enableMultiJurisdiction && effectiveJurisdictions.length > 1 ? normalized.parallelExecution : false,
  }
}
