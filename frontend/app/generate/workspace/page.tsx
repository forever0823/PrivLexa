"use client"

import { useEffect, useMemo, useState } from "react"
import { FileText } from "lucide-react"

import ChatInterface from "@/components/chat-interface"
import {
  buildGenerateConfigHref,
  getGenerationDescription,
  getJurisdictionOption,
  normalizeGenerateJurisdiction,
} from "@/lib/policy-workflows"

export default function GenerateWorkspacePage() {
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<ReturnType<typeof normalizeGenerateJurisdiction>>("CN")

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setSelectedJurisdiction(normalizeGenerateJurisdiction(params.get("jurisdiction")))
  }, [])

  const selectedOption = useMemo(() => getJurisdictionOption(selectedJurisdiction), [selectedJurisdiction])
  const generationDescription = getGenerationDescription(selectedJurisdiction)
  const backHref = buildGenerateConfigHref(selectedJurisdiction)

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f7faf8_0%,#edf7f1_48%,#f8fafc_100%)] py-8">
      <ChatInterface
        title="目标法域隐私政策生成"
        description={generationDescription}
        placeholder={`描述产品类型、收集的数据、处理目的、目标用户地区和第三方服务。我会优先按 ${selectedOption.name} 输出可审查的隐私政策草案。`}
        icon={<FileText className="h-6 w-6 text-white" />}
        color="bg-emerald-600"
        apiEndpoint="/api/generate"
        agentType="privacy_policy_generator"
        backLink={{ href: backHref, label: "返回配置页" }}
        workflowSummary={{
          badge: "第 2 步 / 共 2 步 · 执行生成",
          title: "生成配置摘要",
          items: [
            { label: "目标法域", value: `${selectedOption.name} (${selectedOption.code})` },
            { label: "输出模式", value: selectedJurisdiction === "GLOBAL" ? "全球共同基线版" : "单法域版" },
            { label: "法域策略", value: selectedJurisdiction === "GLOBAL" ? "保守融合" : "严格不混法域" },
            { label: "RAG", value: "默认开启" },
          ],
          note: `${generationDescription}\n\n建议先写清产品功能、数据类型、处理目的、目标市场和第三方 SDK，再补充任何你希望强化或弱化的条款方向。`,
        }}
        generationOptions={{
          jurisdiction: selectedJurisdiction,
          useRag: true,
          summaryLabel: `${selectedOption.name} 作为当前主法域，生成时会优先遵循该法域义务边界。`,
        }}
      />
    </main>
  )
}
