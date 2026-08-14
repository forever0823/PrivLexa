"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, ArrowRight, Globe2, Shield } from "lucide-react"

import { StatCard, SummaryRow } from "@/components/workflow-cards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  buildComplianceWorkspaceHref,
  complianceJurisdictionLabels,
  defaultComplianceOptions,
  getComplianceExecutionConfig,
  normalizeComplianceOptions,
  parseComplianceOptions,
  type ComplianceJurisdiction,
  type ComplianceWorkflowOptions,
} from "@/lib/policy-workflows"

function getConflictModeLabel(mode: "hard" | "soft" | "both") {
  if (mode === "hard") return "规则检测"
  if (mode === "soft") return "语义相似"
  return "混合模式"
}

export default function CompliancePage() {
  const router = useRouter()
  const [options, setOptions] = useState<ComplianceWorkflowOptions>(defaultComplianceOptions)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setOptions(parseComplianceOptions(params))
  }, [])

  const executionConfig = useMemo(() => getComplianceExecutionConfig(options), [options])
  const selectedCount = executionConfig.enabledJurisdictions.length
  const workspaceHref = buildComplianceWorkspaceHref(options)
  const canContinue = selectedCount > 0

  const updateOptions = (updater: (current: ComplianceWorkflowOptions) => ComplianceWorkflowOptions) => {
    setOptions((current) => normalizeComplianceOptions(updater(current)))
  }

  const handleJurisdictionToggle = (jurisdiction: ComplianceJurisdiction, checked: boolean) => {
    updateOptions((current) => {
      if (!current.enableMultiJurisdiction && checked) {
        return {
          ...current,
          selectedJurisdictions: {
            CN: jurisdiction === "CN",
            US: jurisdiction === "US",
            EU: jurisdiction === "EU",
          },
        }
      }

      return {
        ...current,
        selectedJurisdictions: {
          ...current.selectedJurisdictions,
          [jurisdiction]: checked,
        },
      }
    })
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef6ff_48%,#f8fafc_100%)]">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <Link href="/">
            <Button variant="ghost" className="mb-4 rounded-full px-3 text-slate-600 hover:bg-white/80 hover:text-slate-900">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回首页
            </Button>
          </Link>

          <div className="flex flex-col gap-5 rounded-[2rem] border border-white/80 bg-white/85 p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] backdrop-blur sm:p-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-sm text-sky-700">
                  <Shield className="h-4 w-4" />
                  Step 1 / 2 配置检测
                </div>
                
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <StatCard label="已选法域" value={`${selectedCount}`} helper="用于检测覆盖范围" />
                <StatCard
                  label="冲突检测"
                  value={executionConfig.options.enableConflictDetection ? "已开启" : "关闭"}
                  helper="识别条款前后不一致"
                />
                <StatCard label="下一步" value="进入执行页" helper="配置完成后再开始检测" />
              </div>
            </div>

            <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
              <Card className="border-slate-200/80 shadow-none">
                <CardHeader>
                  <CardTitle className="text-lg text-slate-900">检测配置</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-6">
                  <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                      <Globe2 className="h-4 w-4 text-sky-600" />
                      法域范围
                    </div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="multi-jurisdiction"
                        checked={executionConfig.options.enableMultiJurisdiction}
                        onCheckedChange={(checked) =>
                          updateOptions((current) => ({
                            ...current,
                            enableMultiJurisdiction: checked === true,
                          }))
                        }
                      />
                      <Label htmlFor="multi-jurisdiction" className="cursor-pointer text-sm text-slate-700">
                        启用多法域检测
                      </Label>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {(Object.keys(complianceJurisdictionLabels) as ComplianceJurisdiction[]).map((jurisdiction) => (
                        <label
                          key={jurisdiction}
                          htmlFor={`jurisdiction-${jurisdiction}`}
                          className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700 transition hover:border-sky-300 hover:bg-sky-50/50"
                        >
                          <Checkbox
                            id={`jurisdiction-${jurisdiction}`}
                            checked={executionConfig.options.selectedJurisdictions[jurisdiction]}
                            onCheckedChange={(checked) => handleJurisdictionToggle(jurisdiction, checked === true)}
                          />
                          <span>{complianceJurisdictionLabels[jurisdiction]}</span>
                        </label>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="parallel-execution"
                        checked={executionConfig.options.parallelExecution}
                        disabled={!executionConfig.options.enableMultiJurisdiction}
                        onCheckedChange={(checked) =>
                          updateOptions((current) => ({
                            ...current,
                            parallelExecution: checked === true,
                          }))
                        }
                      />
                      <Label htmlFor="parallel-execution" className="cursor-pointer text-sm text-slate-700">
                        并行执行多法域检测
                      </Label>
                    </div>
                  </section>

                  <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                    <div className="text-sm font-medium text-slate-900">冲突检测</div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="conflict-detection"
                        checked={executionConfig.options.enableConflictDetection}
                        onCheckedChange={(checked) =>
                          updateOptions((current) => ({
                            ...current,
                            enableConflictDetection: checked === true,
                          }))
                        }
                      />
                      <Label htmlFor="conflict-detection" className="cursor-pointer text-sm text-slate-700">
                        检查条款之间的表述冲突和逻辑不一致
                      </Label>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {(["hard", "soft", "both"] as const).map((mode) => (
                        <label
                          key={mode}
                          htmlFor={`mode-${mode}`}
                          className={`cursor-pointer rounded-2xl border px-3 py-3 text-sm transition ${
                            executionConfig.options.conflictDetectionMode === mode
                              ? "border-sky-300 bg-sky-50 text-sky-700"
                              : "border-slate-200 bg-white text-slate-700 hover:border-sky-200"
                          }`}
                        >
                          <input
                            id={`mode-${mode}`}
                            type="radio"
                            name="conflict-mode"
                            value={mode}
                            checked={executionConfig.options.conflictDetectionMode === mode}
                            onChange={() =>
                              updateOptions((current) => ({
                                ...current,
                                conflictDetectionMode: mode,
                              }))
                            }
                            className="sr-only"
                          />
                          {getConflictModeLabel(mode)}
                        </label>
                      ))}
                    </div>
                  </section>

                  <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                    <div className="text-sm font-medium text-slate-900">输出格式</div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {(["markdown", "json"] as const).map((format) => (
                        <label
                          key={format}
                          htmlFor={`format-${format}`}
                          className={`cursor-pointer rounded-2xl border px-3 py-3 text-sm transition ${
                            executionConfig.options.outputFormat === format
                              ? "border-slate-900 bg-slate-900 text-white"
                              : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                          }`}
                        >
                          <input
                            id={`format-${format}`}
                            type="radio"
                            name="output-format"
                            value={format}
                            checked={executionConfig.options.outputFormat === format}
                            onChange={() =>
                              updateOptions((current) => ({
                                ...current,
                                outputFormat: format,
                              }))
                            }
                            className="sr-only"
                          />
                          {format === "markdown" ? "Markdown 输出" : "JSON 输出"}
                        </label>
                      ))}
                    </div>
                  </section>
                </CardContent>
              </Card>

              <Card className="border-slate-200/80 shadow-none">
                <CardHeader>
                  <CardTitle className="text-lg text-slate-900">配置摘要</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm text-slate-600">
                  <SummaryRow
                    label="法域范围"
                    value={executionConfig.enabledJurisdictions.length > 0 ? executionConfig.enabledJurisdictions.join(", ") : "未选择"}
                  />
                  <SummaryRow
                    label="冲突检测"
                    value={
                      executionConfig.options.enableConflictDetection
                        ? getConflictModeLabel(executionConfig.options.conflictDetectionMode)
                        : "未启用"
                    }
                  />
                  <SummaryRow label="执行方式" value={executionConfig.parallelExecution ? "并行执行" : "串行执行"} />
                  <SummaryRow label="输出格式" value={executionConfig.options.outputFormat.toUpperCase()} />
                  <div className="rounded-2xl bg-slate-50 p-4 leading-7 text-slate-600">
                    下一步进入检测页后，再上传现有隐私政策全文或直接粘贴文本，系统会按这里确认的配置启动审查。
                  </div>
                  <Button
                    type="button"
                    disabled={!canContinue}
                    onClick={() => router.push(workspaceHref)}
                    className="w-full rounded-2xl bg-sky-600 text-white hover:bg-sky-700"
                  >
                    确认配置，进入检测
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
