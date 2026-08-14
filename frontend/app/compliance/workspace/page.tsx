"use client"

import { useEffect, useMemo, useState } from "react"
import { Shield } from "lucide-react"

import ChatInterface from "@/components/chat-interface"
import {
  buildComplianceConfigHref,
  complianceJurisdictionLabels,
  defaultComplianceOptions,
  getComplianceExecutionConfig,
  parseComplianceOptions,
} from "@/lib/policy-workflows"

function getConflictModeLabel(mode: "hard" | "soft" | "both") {
  if (mode === "hard") return "规则检测"
  if (mode === "soft") return "语义相似"
  return "混合模式"
}

export default function ComplianceWorkspacePage() {
  const [executionConfig, setExecutionConfig] = useState(() => getComplianceExecutionConfig(defaultComplianceOptions))

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setExecutionConfig(getComplianceExecutionConfig(parseComplianceOptions(params)))
  }, [])

  const enabledJurisdictions = executionConfig.enabledJurisdictions
  const backHref = buildComplianceConfigHref(executionConfig.options)

  const complianceDescription = executionConfig.options.enableConflictDetection
    ? executionConfig.options.enableMultiJurisdiction
      ? "按所选法域并结合冲突检测审查隐私政策，定位缺失披露、跨法域差异与潜在矛盾。"
      : "按当前法域检测隐私政策，并重点识别条款冲突、逻辑不一致和高风险表述。"
    : executionConfig.options.enableMultiJurisdiction
      ? "按所选法域审查隐私政策，生成统一的多法域合规结论。"
      : "按当前法域审查隐私政策，定位缺失披露和高风险表述。"

  const jurisdictionLabel = useMemo(
    () =>
      enabledJurisdictions.length > 0
        ? enabledJurisdictions.map((code) => complianceJurisdictionLabels[code]).join(" / ")
        : complianceJurisdictionLabels.CN,
    [enabledJurisdictions],
  )

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef6ff_48%,#f8fafc_100%)] py-8">
      <ChatInterface
        title="合规性检测"
        description={complianceDescription}
        placeholder="粘贴隐私政策全文，或上传文档开始检测。你也可以补充业务类型、目标法域和第三方服务，让结论更具体。"
        icon={<Shield className="h-6 w-6 text-white" />}
        color="bg-sky-600"
        apiEndpoint={executionConfig.activeApiEndpoint}
        agentType={executionConfig.activeAgentType}
        backLink={{ href: backHref, label: "返回配置页" }}
        workflowSummary={{
          badge: "Step 2 / 2 执行检测",
          title: "检测配置摘要",
          description: "以下参数来自配置页确认结果，当前页面只保留执行所需的关键信息。",
          items: [
            { label: "法域范围", value: jurisdictionLabel },
            {
              label: "冲突检测",
              value: executionConfig.options.enableConflictDetection
                ? getConflictModeLabel(executionConfig.options.conflictDetectionMode)
                : "未启用",
            },
            { label: "执行方式", value: executionConfig.parallelExecution ? "并行执行" : "串行执行" },
            { label: "输出格式", value: executionConfig.options.outputFormat.toUpperCase() },
          ],
          note: `${complianceDescription}\n\n建议优先上传现有隐私政策全文，再补充产品类型、用户所在地和第三方服务，这样输出的风险结论和整改建议会更具体。`,
        }}
        complianceOptions={{
          jurisdictions: enabledJurisdictions,
          enableConflictDetection: executionConfig.options.enableConflictDetection,
          conflictDetectionMode: executionConfig.options.conflictDetectionMode,
          parallelExecution: executionConfig.parallelExecution,
          outputFormat: executionConfig.options.outputFormat,
        }}
      />
    </main>
  )
}
