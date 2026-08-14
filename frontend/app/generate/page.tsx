"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, ArrowRight, Globe2, Sparkles } from "lucide-react"

import { StatCard, SummaryRow } from "@/components/workflow-cards"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  buildGenerateWorkspaceHref,
  fallbackJurisdictions,
  getGenerationDescription,
  getJurisdictionOption,
  type GenerateJurisdiction,
  type JurisdictionOption,
  normalizeGenerateJurisdiction,
} from "@/lib/policy-workflows"

const supportedGenerateJurisdictions = new Set<GenerateJurisdiction>(["CN", "US", "EU", "GLOBAL"])

export default function GeneratePage() {
  const router = useRouter()
  const [jurisdictions, setJurisdictions] = useState<JurisdictionOption[]>(fallbackJurisdictions)
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<GenerateJurisdiction>("CN")

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setSelectedJurisdiction(normalizeGenerateJurisdiction(params.get("jurisdiction")))
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadJurisdictions = async () => {
      try {
        const response = await fetch("/api/v2/jurisdictions")
        const data = await response.json()
        if (!data?.success || !Array.isArray(data.jurisdictions) || cancelled) {
          return
        }

        const fetched = data.jurisdictions
          .map((item: JurisdictionOption) => ({
            code: item.code,
            name: item.name,
            description: item.description,
            laws: item.laws,
          }))
          .filter((item: JurisdictionOption): item is JurisdictionOption => supportedGenerateJurisdictions.has(item.code))

        const merged = new Map<GenerateJurisdiction, JurisdictionOption>(
          fetched.map((item: JurisdictionOption): [GenerateJurisdiction, JurisdictionOption] => [item.code, item]),
        )
        if (!merged.has("GLOBAL")) {
          merged.set("GLOBAL", fallbackJurisdictions.find((item: JurisdictionOption) => item.code === "GLOBAL")!)
        }

        setJurisdictions(Array.from(merged.values()))
      } catch {
        if (!cancelled) {
          setJurisdictions(fallbackJurisdictions)
        }
      }
    }

    void loadJurisdictions()

    return () => {
      cancelled = true
    }
  }, [])

  const selectedOption = useMemo(
    () => jurisdictions.find((item) => item.code === selectedJurisdiction) || getJurisdictionOption(selectedJurisdiction),
    [jurisdictions, selectedJurisdiction],
  )

  const generationDescription = getGenerationDescription(selectedJurisdiction)
  const workspaceHref = buildGenerateWorkspaceHref(selectedJurisdiction)

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef7f2_52%,#f8fafc_100%)]">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <Link href="/">
            <Button variant="ghost" className="mb-4 rounded-full px-3 text-slate-600 hover:bg-white/80 hover:text-slate-900">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回首页
            </Button>
          </Link>

          <div className="flex flex-col gap-5 rounded-[2rem] border border-white/80 bg-white/88 p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] backdrop-blur sm:p-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-700">
                  <Sparkles className="h-4 w-4" />
                  第 1 步 / 共 2 步 · 配置生成
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <StatCard label="当前法域" value={selectedOption.code} helper={selectedOption.name} />
                <StatCard
                  label="生成策略"
                  value={selectedJurisdiction === "GLOBAL" ? "统一基线" : "单法域"}
                  helper="默认保持目标法域边界"
                />
                <StatCard label="下一步" value="进入执行页" helper="配置完成后再开始生成" />
              </div>
            </div>

            <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
              <Card className="border-slate-200/80 shadow-none">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg text-slate-900">
                    <Globe2 className="h-5 w-5 text-emerald-600" />
                    目标法域
                  </CardTitle>

                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  {jurisdictions.map((item) => {
                    const active = item.code === selectedJurisdiction
                    return (
                      <button
                        key={item.code}
                        type="button"
                        onClick={() => setSelectedJurisdiction(item.code)}
                        className={`rounded-3xl border px-4 py-4 text-left transition ${
                          active
                            ? "border-emerald-300 bg-emerald-50 shadow-sm"
                            : "border-slate-200 bg-white hover:border-emerald-200 hover:bg-emerald-50/40"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-base font-semibold text-slate-900">{item.name}</p>
                            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">{item.code}</p>
                          </div>
                          {active && (
                            <Badge variant="outline" className="rounded-full border-emerald-200 bg-white text-emerald-700">
                              已选中
                            </Badge>
                          )}
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-600">{item.description}</p>
                        {item.laws?.length ? (
                          <p className="mt-3 text-xs text-slate-500">关键规则：{item.laws.join(" / ")}</p>
                        ) : null}
                      </button>
                    )
                  })}
                </CardContent>
              </Card>

              <Card className="border-slate-200/80 shadow-none">
                <CardHeader>
                  <CardTitle className="text-lg text-slate-900">配置摘要</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm text-slate-600">
                  <SummaryRow label="目标法域" value={`${selectedOption.name} (${selectedOption.code})`} />
                  <SummaryRow label="输出模式" value={selectedJurisdiction === "GLOBAL" ? "全球共同基线版" : "单法域版"} />
                  <SummaryRow label="法域策略" value={selectedJurisdiction === "GLOBAL" ? "保守融合" : "严格不混法域"} />
                  <div className="rounded-2xl bg-slate-50 p-4 leading-7 text-slate-600">{generationDescription}</div>
                  <Button
                    type="button"
                    onClick={() => router.push(workspaceHref)}
                    className="w-full rounded-2xl bg-emerald-600 text-white hover:bg-emerald-700"
                  >
                    确认配置，进入生成
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
