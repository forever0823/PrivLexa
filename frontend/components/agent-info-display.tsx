"use client"

import type React from "react"

import { Eye, FileText, Info, Shield } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface AgentInfoDisplayProps {
  agentType: string
  className?: string
  compact?: boolean
  action?: React.ReactNode
  statusLabel?: string
  statusClassName?: string
  statusNote?: string
}

const agentConfigs = {
  privacy_policy_generator: {
    name: "生成 Agent",
    description: "根据业务上下文、目标法域和已上传材料组织一版可继续迭代的隐私政策草案。",
    icon: <FileText className="h-5 w-5" />,
    iconClassName: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
    badgeClassName: "border-emerald-200 bg-emerald-50 text-emerald-700",
    capabilities: ["按法域整理政策结构与义务边界", "结合上下文补全数据处理与用户权利说明", "支持基于现有材料继续追问和细化"],
  },
  compliance_checker: {
    name: "合规审查 Agent",
    description: "针对单法域检查现有政策的披露完整性、权利机制和高风险表述。",
    icon: <Shield className="h-5 w-5" />,
    iconClassName: "bg-sky-50 text-sky-700 ring-1 ring-sky-100",
    badgeClassName: "border-sky-200 bg-sky-50 text-sky-700",
    capabilities: ["识别缺失条款和告知盲区", "定位高风险或模糊表述", "输出更接近整改清单的结论"],
  },
  compliance_checker_multi: {
    name: "多法域审查 Agent",
    description: "并行比对多法域要求，适合统一政策版本的跨区域审查。",
    icon: <Shield className="h-5 w-5" />,
    iconClassName: "bg-sky-50 text-sky-700 ring-1 ring-sky-100",
    badgeClassName: "border-sky-200 bg-sky-50 text-sky-700",
    capabilities: ["覆盖多法域义务清单", "识别共同缺口和法域差异", "支持输出统一整改建议"],
  },
  conflict_detector: {
    name: "冲突检测 Agent",
    description: "聚焦条款前后冲突、逻辑矛盾和重复承诺，适合发布前复核。",
    icon: <Shield className="h-5 w-5" />,
    iconClassName: "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
    badgeClassName: "border-amber-200 bg-amber-50 text-amber-700",
    capabilities: ["检测规则冲突与语义冲突", "识别重复承诺与边界不一致", "辅助整理高风险修订点"],
  },
  readability_checker: {
    name: "可读性优化 Agent",
    description: "关注文本清晰度和结构层级，适合把政策写得更易读、更易理解。",
    icon: <Eye className="h-5 w-5" />,
    iconClassName: "bg-violet-50 text-violet-700 ring-1 ring-violet-100",
    badgeClassName: "border-violet-200 bg-violet-50 text-violet-700",
    capabilities: ["标记长句和术语堆叠", "定位重点信息不突出的段落", "给出更直白的改写方向"],
  },
} as const

export default function AgentInfoDisplay({
  agentType,
  className,
  compact = false,
  action,
  statusLabel,
  statusClassName,
  statusNote,
}: AgentInfoDisplayProps) {
  const config = agentConfigs[agentType as keyof typeof agentConfigs]

  if (!config) {
    return (
      <Card className={cn("border-slate-200 bg-white shadow-none", className)}>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Info className="h-4 w-4" />
            <span>未识别的 Agent 类型：{agentType}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={cn("overflow-hidden border-slate-200 bg-white shadow-none", className)}>
      <CardHeader className={cn("space-y-4 p-5", compact && "space-y-3 p-4 pb-3")}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className={cn("flex items-start gap-4", compact && "gap-3")}>
            <div
              className={cn(
                "flex h-12 w-12 flex-none items-center justify-center rounded-2xl",
                compact && "h-10 w-10 rounded-xl",
                config.iconClassName,
              )}
            >
              {config.icon}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className={cn("text-base text-slate-950", compact && "text-[15px]")}>{config.name}</CardTitle>
                <Badge variant="outline" className={config.badgeClassName}>
                  当前执行
                </Badge>
                {statusLabel ? (
                  <Badge variant="outline" className={cn("border-slate-200 bg-slate-50 text-slate-600", statusClassName)}>
                    {statusLabel}
                  </Badge>
                ) : null}
              </div>
              <p className={cn("mt-2 text-sm leading-6 text-slate-600", compact && "mt-1.5 text-[13px] leading-5")}>{config.description}</p>
              {statusNote ? <p className="mt-1.5 text-xs leading-5 text-slate-500">{statusNote}</p> : null}
            </div>
          </div>
          {action ? <div className="flex flex-none items-center gap-2 self-start">{action}</div> : null}
        </div>
      </CardHeader>
      <CardContent className={cn("p-5 pt-0", compact && "p-4 pt-0")}>
        <div className={cn(compact ? "grid gap-2 sm:grid-cols-2 xl:grid-cols-3" : "space-y-2")}>
          {config.capabilities.map((capability) => (
            <div
              key={capability}
              className={cn(
                "flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-3 py-3 text-sm text-slate-600",
                compact && "h-full gap-2.5 rounded-xl px-3 py-2.5 text-[13px] leading-5",
              )}
            >
              <div className="mt-1.5 h-1.5 w-1.5 flex-none rounded-full bg-slate-400" />
              <span>{capability}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
