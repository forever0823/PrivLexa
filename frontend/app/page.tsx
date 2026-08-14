import Link from "next/link"
import {
  ArrowRight,
  BadgeCheck,
  FileStack,
  Globe2,
  LockKeyhole,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const coreActions = [
  {
    href: "/generate",
    eyebrow: "起草",
    title: "生成隐私政策首稿",
    description:
      "以法规知识图谱为底座，先检索目标法域的条款、义务和法域画像，再生成可继续修订的政策首稿。",
    points: [
      "默认启用 RAG，把检索到的法规条款作为生成约束，而不是只靠通用模型自由生成",
      "生成提示会注入法域嵌入、合规要点和义务锚点，保持法域边界清晰",
      "缺失业务事实时保留 [待确认：具体事实] 占位，适合从零起草或版本迭代前快速搭建基线",
    ],
    capabilityLabel: "底层链路",
    capabilitySummary: "知识图谱 + RAG 检索 + 法域嵌入",
    capabilities: ["法律-条款-义务-概念", "RAG 开启", "证据摘要", "可选嵌入重排"],
    icon: FileStack,
    accent: "from-emerald-500/18 via-emerald-500/10 to-transparent",
    iconWrap: "bg-emerald-500 text-white",
    buttonClass: "bg-emerald-600 text-white hover:bg-emerald-700",
    cta: "进入生成",
  },
  {
    href: "/compliance",
    eyebrow: "审查",
    title: "执行合规检测",
    description:
      "基于同一套法规知识图谱和法域义务清单，对现有政策做逐项审查，定位缺失披露、冲突和高风险表达。",
    points: [
      "按 CN / US / EU 义务清单逐项核查覆盖情况，并统一归一到已覆盖、缺失、冲突、高风险等状态",
      "支持多法域并行检测，适合一份政策同时面向多个地区时快速拉出统一结论",
      "可叠加规则冲突与语义冲突检测，把问题直接回收到具体条款修订和整改建议",
    ],
    capabilityLabel: "检测引擎",
    capabilitySummary: "知识图谱 + 义务审查 + 并行校验",
    capabilities: ["法域义务", "并行审查", "冲突检测", "Markdown 报告"],
    icon: ScanSearch,
    accent: "from-sky-500/18 via-sky-500/10 to-transparent",
    iconWrap: "bg-sky-600 text-white",
    buttonClass: "bg-sky-600 text-white hover:bg-sky-700",
    cta: "进入检测",
  },
]

const workflowSteps = [
  {
    index: "01",
    title: "整理输入上下文",
    description: "先准备产品类型、收集数据、处理目的、用户地区和第三方服务，减少后续反复追问。",
  },
  {
    index: "02",
    title: "生成或导入文本",
    description: "新项目直接生成首稿，存量项目则把现有政策贴入系统作为检测对象。",
  },
  {
    index: "03",
    title: "回到条款修订",
    description: "根据检测结论和待确认项回改文本，把结果沉淀成下一轮可复用的政策版本。",
  },
]

const productSignals = [
  { label: "核心入口", value: "2 个", helper: "隐私政策生成与合规检测" },
  { label: "法域覆盖", value: "CN / US / EU", helper: "面向多法域政策工作流" },
  { label: "输出目标", value: "结构化可复核", helper: "便于法务 , 产品 , 研发协同" },
]


export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[linear-gradient(180deg,#f3efe7_0%,#faf7f1_44%,#eef4ff_100%)] text-slate-950">
      <div
        aria-hidden="true"
        className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(15,23,42,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.06)_1px,transparent_1px)] [background-size:72px_72px] [mask-image:linear-gradient(180deg,rgba(0,0,0,0.55),transparent_78%)]"
      />
      <div aria-hidden="true" className="absolute left-[-8rem] top-24 h-72 w-72 rounded-full bg-emerald-300/35 blur-3xl" />
      <div aria-hidden="true" className="absolute right-[-6rem] top-12 h-80 w-80 rounded-full bg-sky-300/30 blur-3xl" />
      <div aria-hidden="true" className="absolute bottom-0 right-1/4 h-64 w-64 rounded-full bg-amber-200/35 blur-3xl" />

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between rounded-full border border-white/70 bg-white/72 px-4 py-3 shadow-[0_18px_50px_-32px_rgba(15,23,42,0.45)] backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <div className="relative flex h-11 w-11 items-center justify-center rounded-full bg-slate-950 text-white">
              <ShieldCheck className="h-5 w-5" />
              <LockKeyhole className="absolute h-3.5 w-3.5 opacity-85" />
            </div>
            <div>
              <p className="text-s font-semibold tracking-[0.18em] text-slate-500">PrivLexa · 隐律智策</p>
            </div>
          </div>

          <nav aria-label="核心功能" className="hidden items-center gap-2 md:flex">
            <Link
              href="/generate"
              className="rounded-full px-4 py-2 text-sm text-slate-600 transition hover:bg-slate-950 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              生成
            </Link>
            <Link
              href="/compliance"
              className="rounded-full px-4 py-2 text-sm text-slate-600 transition hover:bg-slate-950 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              合规检测
            </Link>
          </nav>
        </header>

        <section className="grid flex-1 gap-8 py-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-start lg:py-10">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-300/70 bg-white/80 px-4 py-2 text-sm text-slate-700 shadow-sm backdrop-blur">
              <Sparkles className="h-4 w-4 text-amber-500" />
              聚焦两个动作：生成基线、审查风险
            </div>

            <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-[1.3] tracking-loose text-slate-950 sm:text-4xl lg:text-5xl">
              面向多法域融合的隐私政策生成与合规检测系统
              <span className="block text-4xl text-slate-600"></span>
            </h1>


            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="rounded-full bg-slate-950 px-7 text-white hover:bg-slate-800">
                <Link href="/generate">
                  开始生成
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="rounded-full border-slate-300 bg-white/80 px-7 text-slate-800 hover:bg-white"
              >
                <Link href="/compliance">合规检测</Link>
              </Button>
            </div>

            <dl className="mt-10 grid gap-3 sm:grid-cols-3">
              {productSignals.map((item) => (
                <div key={item.label} className="rounded-[1.5rem] border border-white/80 bg-white/78 p-4 shadow-sm backdrop-blur">
                  <dt className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">{item.label}</dt>
                  <dd className="mt-2 text-2xl font-semibold text-slate-950">{item.value}</dd>
                  <dd className="mt-2 text-sm leading-6 text-slate-600">{item.helper}</dd>
                </div>
              ))}
            </dl>
          </div>

          <aside className="grid gap-5">
            <Card className="overflow-hidden rounded-[2rem] border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(247,250,252,0.88)_100%)] shadow-[0_26px_90px_-52px_rgba(15,23,42,0.55)] backdrop-blur">
              <CardHeader className="pb-4">
                <div className="inline-flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                  <Workflow className="h-3.5 w-3.5" />
                  推荐工作流
                </div>
                
              </CardHeader>
              <CardContent className="space-y-4">
                {workflowSteps.map((step) => (
                  <div
                    key={step.index}
                    className="grid gap-3 rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-4 sm:grid-cols-[auto_1fr]"
                  >
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-950 text-sm font-semibold text-white">
                      {step.index}
                    </div>
                    <div>
                      <p className="text-base font-semibold text-slate-900">{step.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{step.description}</p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

          </aside>
        </section>

        <section aria-labelledby="core-actions-title" className="pb-8 lg:pb-12">
          <div className="mb-6 flex items-end justify-between gap-4">

          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            {coreActions.map(
              ({
                href,
                eyebrow,
                title,
                description,
                points,
                capabilityLabel,
                capabilitySummary,
                capabilities,
                icon: Icon,
                accent,
                iconWrap,
                buttonClass,
                cta,
              }) => (
              <Card
                key={title}
                className="overflow-hidden rounded-[2rem] border-white/80 bg-white/86 shadow-[0_26px_90px_-54px_rgba(15,23,42,0.5)] backdrop-blur"
              >
                <div className={`h-24 bg-gradient-to-r ${accent}`} />
                <CardHeader className="gap-5 pt-0">
                  <div className="-mt-10 flex items-start justify-between gap-4">
                    <div className={`flex h-16 w-16 items-center justify-center rounded-[1.25rem] ${iconWrap} shadow-lg shadow-slate-900/10`}>
                      <Icon className="h-7 w-7" />
                    </div>
                    <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                      {eyebrow}
                    </span>
                  </div>
                  <div className="space-y-3">
                    <CardTitle className="text-3xl leading-tight text-slate-950">{title}</CardTitle>
                    <CardDescription className="max-w-2xl text-sm leading-7 text-slate-600">{description}</CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  <ul className="space-y-3 text-sm text-slate-700">
                    {points.map((point) => (
                      <li key={point} className="flex items-start gap-3">
                        <span className="mt-1 h-2.5 w-2.5 rounded-full bg-slate-950" />
                        <span className="leading-6">{point}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{capabilityLabel}</p>
                    <p className="mt-2 text-sm font-medium text-slate-900">{capabilitySummary}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {capabilities.map((item) => (
                        <span
                          key={item}
                          className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>


                  <Button asChild size="lg" className={`w-full rounded-2xl ${buttonClass}`}>
                    <Link href={href}>
                      {cta}
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
