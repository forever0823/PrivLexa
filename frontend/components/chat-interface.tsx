"use client"

import type React from "react"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  Brain,
  CheckCircle2,
  FileText,
  Loader2,
  RefreshCw,
  Send,
  User,
  X,
} from "lucide-react"

import AgentInfoDisplay from "./agent-info-display"
import FileUploadButton from "./file-upload-button"
import MarkdownRenderer from "./markdown-renderer"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

interface UploadedFile {
  id: string
  name: string
  size: number
  type: string
  content?: string
  uploadTime: Date
}

interface BackendStatus {
  success: boolean
  backend_status: string
  error?: string
  available_agents?: Array<{ name: string; type: string; status: string }>
}

interface GenerationOptions {
  jurisdiction?: string
  useRag?: boolean
  summaryLabel?: string
}

interface BackLink {
  href: string
  label: string
}

interface WorkflowSummaryItem {
  label: string
  value: string
}

interface WorkflowSummary {
  badge?: string
  title: string
  description?: string
  items: WorkflowSummaryItem[]
  note?: string
}

interface ChatInterfaceProps {
  title: string
  description: string
  placeholder: string
  icon: React.ReactNode
  color: string
  apiEndpoint: string
  agentType: string
  backLink?: BackLink
  workflowSummary?: WorkflowSummary
  complianceOptions?: {
    jurisdictions?: string[]
    enableConflictDetection?: boolean
    conflictDetectionMode?: "hard" | "soft" | "both"
    parallelExecution?: boolean
    outputFormat?: "markdown" | "json"
  }
  generationOptions?: GenerationOptions
}

const agentCopy = {
  privacy_policy_generator: {
    name: "生成执行台",
    emptyTitle: "描述业务、数据流和目标法域，开始生成隐私政策草案。",
    emptyHint: "支持上传 TXT、PDF、DOC、DOCX，也可以直接说明产品类型、数据处理范围和目标市场。",
    uploadPrompt: "我已上传《{name}》，请基于文件内容补全业务背景并生成一版更完整的隐私政策草案。",
    guidance: [
      "先写清产品类型、用户对象和数据处理目的。",
      "尽量列出收集的数据类别、第三方 SDK 和目标法域。",
      "如果已有旧版政策或需求文档，直接上传会更高效。",
    ],
  },
  compliance_checker: {
    name: "单法域审查台",
    emptyTitle: "上传或粘贴现有隐私政策，开始做单法域合规审查。",
    emptyHint: "适合检查披露是否完整、权利机制是否缺失，以及高风险表述是否需要修改。",
    uploadPrompt: "我已上传《{name}》，请按当前法域检查这份隐私政策的合规风险和缺失条款。",
    guidance: [
      "优先上传完整政策正文，不要只给截图或节选。",
      "补充产品类型、目标用户地区和第三方服务情况。",
      "如果只关心某类风险，可以在问题里直接指出重点。",
    ],
  },
  compliance_checker_multi: {
    name: "多法域审查台",
    emptyTitle: "上传或粘贴现有隐私政策，开始做多法域合规审查。",
    emptyHint: "系统会结合当前选定的法域范围输出更具体的缺口、差异和统一整改建议。",
    uploadPrompt: "我已上传《{name}》，请按当前选定法域检查这份隐私政策的合规风险和缺失条款。",
    guidance: [
      "多法域任务优先提供完整正文和目标市场范围。",
      "如果某个法域优先级更高，可以在问题里明确说明。",
      "需要统一版本还是分法域建议，也可以直接说明。",
    ],
  },
} as const

const fallbackCopy = {
  name: "分析执行台",
  emptyTitle: "上传材料或直接描述任务，开始本轮分析。",
  emptyHint: "你可以先补充业务背景、目标法域和希望的输出形式。",
  uploadPrompt: "我已上传《{name}》，请基于文件内容继续处理当前任务。",
  guidance: ["优先提供完整材料。", "补充任务目标和范围。", "说明你最关心的风险点。"],
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(date: Date) {
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

function looksLikeCollapsedMarkdown(content: string) {
  const normalized = content.replace(/\r\n?/g, "\n")
  const newlineCount = (normalized.match(/\n/g) || []).length
  const headingCount = (normalized.match(/#{1,6}/g) || []).length
  const bulletCount = (normalized.match(/-\S/g) || []).length
  const orderedCount = (normalized.match(/\b\d+\.\S/g) || []).length

  return (
    /[^\n](#{1,6})(?=\S)/.test(normalized) ||
    ((headingCount >= 2 || bulletCount >= 4 || orderedCount >= 4) && newlineCount <= 6)
  )
}

function repairCollapsedMarkdown(content: string) {
  if (!content || !looksLikeCollapsedMarkdown(content)) return content

  let normalized = content.replace(/\r\n?/g, "\n")
  const metadataLabels = "(?:更新日期|生效日期|发布日期|版本号|最后更新|生效时间)"
  const narrativeStarts = "(?:欢迎您|我们|本政策|您可以|在您|由于|如果|当您|圈聊|深圳微聚|CircleTalk)"

  normalized = normalized.replace(/\s*(---+)\s*/g, "\n\n$1\n\n")
  normalized = normalized.replace(/([^\n])\s*(#{1,6})(?=\S)/g, "$1\n\n$2 ")
  normalized = normalized.replace(/(^|\n)(#{1,6})(?=\S)/g, "$1$2 ")
  normalized = normalized.replace(/(^|\n)(#{1,6})\s*(\d+)\./g, "$1$2 $3.")
  normalized = normalized.replace(/(^|\n)(#{1,6})\s*([一二三四五六七八九十]+、)/g, "$1$2 $3")
  normalized = normalized.replace(/(^|\n)(#{1,6}[^\n]+?)(?=(-\s*(?=(?:\*\*|[A-Za-z\u4e00-\u9fff\[]))))/g, "$1$2\n")
  normalized = normalized.replace(
    new RegExp(`(^|\\n)(#{1,6}\\s*[^\\n]{1,80}?)(?=(${metadataLabels}|\\d+\\.\\d+(?=[A-Za-z\\u4e00-\\u9fff])|${narrativeStarts}))`, "g"),
    "$1$2\n\n",
  )
  normalized = normalized.replace(
    new RegExp(`([^\\n])(?=(${metadataLabels})[:：])`, "g"),
    "$1\n",
  )
  normalized = normalized.replace(
    new RegExp(`((${metadataLabels})[:：][^\\n]{0,120}?)(?=(${metadataLabels})[:：])`, "g"),
    "$1\n",
  )
  normalized = normalized.replace(/([\uFF1A:\u3002\uFF1B])\s*((?:-\s*|(?:\d+\.\s*))(?=(?:\*\*|[A-Za-z\u4e00-\u9fff\[])))/g, "$1\n$2")
  normalized = normalized.replace(/([^\n])(?=(\d+\.\d+(?=[A-Za-z\u4e00-\u9fff])))/g, "$1\n\n")
  normalized = normalized.replace(/([^\n])(?=([一二三四五六七八九十]+、))/g, "$1\n\n")
  normalized = normalized.replace(/([^\n])(\*{2,3})(?=(?:更新日期|生效日期|发布日期|版本号))/g, "$1\n\n")
  normalized = normalized.replace(/(^|\n)-(?=\S)/g, "$1- ")
  normalized = normalized.replace(/(^|\n)(\d+)\.(?=\S)/g, "$1$2. ")
  normalized = normalized.replace(/\n{3,}/g, "\n\n")

  return normalized.trim()
}

function normalizeMalformedPolicyMarkdown(content: string) {
  if (!content) return content

  const cjkNumerals = "\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\u516d\\u4e03\\u516b\\u4e5d\\u5341"
  const metadataLabels = "(?:\\u66F4\\u65B0\\u65E5\\u671F|\\u751F\\u6548\\u65E5\\u671F|\\u53D1\\u5E03\\u65E5\\u671F|\\u7248\\u672C\\u53F7|\\u6700\\u540E\\u66F4\\u65B0|\\u751F\\u6548\\u65F6\\u95F4)"
  const narrativeStarts = "(?:\\u6B22\\u8FCE\\u60A8|\\u6211\\u4EEC|\\u672C\\u9690\\u79C1\\u653F\\u7B56|\\u672C\\u653F\\u7B56|\\u60A8\\u53EF\\u4EE5|\\u5728\\u60A8|\\u7531\\u4E8E|\\u5982\\u679C|\\u5F53\\u60A8|\\u5708\\u804A|\\u6DF1\\u5733\\u5FAE\\u805A|CircleTalk)"
  const fieldLabels = ["\\u751F\\u6548\\u65E5\\u671F", "\\u4E0A\\u6B21\\u66F4\\u65B0", "\\u66F4\\u65B0\\u65E5\\u671F", "\\u53D1\\u5E03\\u65E5\\u671F"]

  let normalized = content.replace(/\r\n?/g, "\n").replace(/\u00A0/g, " ")

  // 兼容旧版后端生成的英文占位符，统一转换为中文。
  normalized = normalized.replace(/\[TO_BE_CONFIRMED:\*\*\s*/g, "[待确认：")
  normalized = normalized.replace(/\[TO_BE_CONFIRMED:\s*/g, "[待确认：")
  normalized = normalized.replace(/(^|\n)(#{1,6}\s+.+?)\*{3,}\s*$/gm, "$1$2")
  normalized = normalized.replace(
    /(^|\n)([A-Za-z\u4e00-\u9fff（）()]{2,20})\*\*[:\uFF1A]\s*(\[[^\]\n]+\])\*\*/g,
    "$1- **$2：** $3",
  )
  normalized = normalized.replace(
    /(\[[^\]\n]+\])(?=(?:[A-Za-z\u4e00-\u9fff（）()]{2,20}\*\*[:\uFF1A]|\u5F15\u8A00\*\*))/g,
    "$1\n\n",
  )
  normalized = normalized.replace(/(^|\n)\s*(#{1,5})\s+#\s*/g, (_, prefix, hashes) => `${prefix}${hashes}# `)
  normalized = normalized.replace(/(^|\n)(\d+)\.\s+(\d+)(?=\S)/g, "$1$2.$3 ")
  normalized = normalized.replace(/^(#{1,6}[^\n*]+?)\*{2,}\s*$/gm, "$1")
  for (const label of fieldLabels) {
    normalized = normalized.replace(
      new RegExp(`(^|\\n)(${label})\\n\\*\\n-\\s*\\*\\*[:\\uFF1A]\\s*(\\[[^\\]\\n]+\\])\\*\\*`, "g"),
      "$1- **$2：** $3",
    )
    normalized = normalized.replace(
      new RegExp(`(^|\\n)(${label})\\*\\*[:\\uFF1A]\\s*(\\[[^\\]\\n]+\\])\\*\\*`, "g"),
      "$1- **$2：** $3",
    )
    normalized = normalized.replace(
      new RegExp(`(^|\\n)\\*\\*(${label})\\*\\*[:\\uFF1A]\\s*(\\[[^\\]\\n]+\\])`, "g"),
      "$1- **$2：** $3",
    )
  }
  normalized = normalized.replace(/(\[[^\]\n]+\])(?=(?:\u4E0A\u6B21\u66F4\u65B0|\u66F4\u65B0\u65E5\u671F|\u53D1\u5E03\u65E5\u671F|\u5F15\u8A00))/g, "$1\n\n")
  normalized = normalized.replace(/(^|\n)(\u5F15\u8A00)\*\*(?=\S)/g, "$1**$2**\n\n")
  normalized = normalized.replace(/(^|\n)(\u5F15\u8A00)(?=\S)/g, "$1**$2**\n\n")
  normalized = normalized.replace(/(\*\*\u5F15\u8A00\*\*)(?=\S)/g, "$1\n\n")
  normalized = normalized.replace(
    new RegExp(`(${metadataLabels}[:\\uFF1A]\\*\\*[^\\n*]{2,40}?)(?=${narrativeStarts})`, "g"),
    "$1**\n\n",
  )
  normalized = normalized.replace(
    new RegExp(`(${metadataLabels}[:\\uFF1A][^\\n]{2,40}?)(?=${narrativeStarts})`, "g"),
    "$1\n\n",
  )
  normalized = normalized.replace(
    new RegExp(`([^\\n])(?=([${cjkNumerals}]+、))`, "g"),
    "$1\n\n",
  )
  normalized = normalized.replace(/([^\n])(?=(\*{1,3}[^*\n:\[\]]{1,60}[\uFF1A:]\*{0,2}))/g, "$1\n")
  normalized = normalized.replace(
    /(^|\n)\s*\*{1,3}([^*\n:\[\]]{1,60}[\uFF1A:])\*{0,2}\s*/g,
    "$1- **$2** ",
  )
  normalized = normalized.replace(/\|\|(?=\s*\|?:?-{2,})/g, "|\n|")
  normalized = normalized.replace(/\n\s*\|\s*:\s*-{2,}\s*/g, "\n| --- ")
  normalized = normalized.replace(/(^|\n)\s*-\s*$/gm, "")
  normalized = normalized.replace(/(^|\n)\s*\*\s*$/gm, "")
  normalized = normalized.replace(/\n{3,}/g, "\n\n")

  return normalized.trim()
}

function SummaryCard({
  title,
  description,
  action,
  children,
  className,
  contentClassName,
}: {
  title: string
  description?: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
  contentClassName?: string
}) {
  return (
    <Card className={cn("border-slate-200 bg-white shadow-none", className)}>
      <CardContent className={cn("p-4", contentClassName)}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-slate-950">{title}</p>
            {description ? <p className="mt-1 text-[13px] leading-5 text-slate-500">{description}</p> : null}
          </div>
          {action}
        </div>
        <div className="mt-3">{children}</div>
      </CardContent>
    </Card>
  )
}

export default function ChatInterface({
  title,
  description,
  placeholder,
  icon,
  color,
  apiEndpoint,
  agentType,
  backLink,
  workflowSummary,
  complianceOptions,
  generationOptions,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isThinking, setIsThinking] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [currentFileContent, setCurrentFileContent] = useState("")
  const [backendStatus, setBackendStatus] = useState<BackendStatus | null>(null)
  const [isCheckingStatus, setIsCheckingStatus] = useState(true)
  const [isTesting, setIsTesting] = useState(false)
  const messageContainerRef = useRef<HTMLDivElement>(null)

  const copy = useMemo(() => agentCopy[agentType as keyof typeof agentCopy] ?? fallbackCopy, [agentType])

  const checkBackendStatus = async () => {
    try {
      const response = await fetch("/api/status")
      setBackendStatus(await response.json())
    } catch {
      setBackendStatus({ success: false, backend_status: "disconnected", error: "当前无法连接到后端服务。" })
    }
  }

  const testConnection = async () => {
    setIsTesting(true)
    try {
      const response = await fetch("/api/test-connection", { method: "POST" })
      const data = await response.json()
      if (!data.success) throw new Error(data.error || "连接测试失败")
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: "连接测试成功。后端服务在线。", timestamp: new Date() },
      ])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `连接测试失败：${error instanceof Error ? error.message : "未知错误"}`,
          timestamp: new Date(),
        },
      ])
    } finally {
      setIsTesting(false)
      void checkBackendStatus()
    }
  }

  useEffect(() => {
    const run = async () => {
      setIsCheckingStatus(true)
      await checkBackendStatus()
      setIsCheckingStatus(false)
    }
    void run()
    const timer = window.setInterval(() => void checkBackendStatus(), 30000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (messageContainerRef.current) {
      messageContainerRef.current.scrollTop = messageContainerRef.current.scrollHeight
    }
  }, [messages, isLoading, isThinking])

  const handleSubmit = async (event: { preventDefault: () => void }) => {
    event.preventDefault()
    const trimmedInput = input.trim()
    if ((!trimmedInput && !currentFileContent) || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedInput || "请基于已上传文件继续处理当前任务。",
      timestamp: new Date(),
    }
    const assistantMessageId = crypto.randomUUID()

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "", timestamp: new Date() },
    ])
    setInput("")
    setIsLoading(true)
    setIsThinking(true)

    try {
      const policyText = currentFileContent || userMessage.content
      const isConflictEndpoint = apiEndpoint.includes("/detect-conflicts")
      const isComplianceEndpoint = apiEndpoint.includes("/compliance")
      const isGenerationFlow = agentType === "privacy_policy_generator" || apiEndpoint.includes("/generate")
      const requestBody: Record<string, unknown> = {
        message: userMessage.content,
        fileContent: currentFileContent,
        agent_type: agentType,
        context: {
          original_message: userMessage.content,
          file_uploaded: Boolean(currentFileContent),
          analysis_type: agentType,
          uploaded_files: uploadedFiles.map((file) => ({ name: file.name, size: file.size, type: file.type })),
          compliance_options: complianceOptions,
          generation_options: generationOptions,
        },
      }

      if (isConflictEndpoint) {
        requestBody.policy_text = policyText
        requestBody.privacy_policy = policyText
        requestBody.jurisdiction = complianceOptions?.jurisdictions?.[0] || "CN"
        requestBody.detection_mode = complianceOptions?.conflictDetectionMode || "both"
        requestBody.include_suggestions = true
      } else if (isComplianceEndpoint) {
        requestBody.policy_text = policyText
        requestBody.privacy_policy = policyText
        requestBody.jurisdictions = complianceOptions?.jurisdictions?.length ? complianceOptions.jurisdictions : ["CN"]
        requestBody.parallel_execution = complianceOptions?.parallelExecution !== false
        requestBody.return_markdown = complianceOptions?.outputFormat !== "json"
        requestBody.enable_conflict_detection = complianceOptions?.enableConflictDetection === true
        requestBody.detection_mode = complianceOptions?.conflictDetectionMode || "both"
      } else if (complianceOptions) {
        if (complianceOptions.jurisdictions?.length) requestBody.jurisdictions = complianceOptions.jurisdictions
        if (complianceOptions.parallelExecution !== undefined) requestBody.parallel_execution = complianceOptions.parallelExecution
        if (complianceOptions.outputFormat) requestBody.return_markdown = complianceOptions.outputFormat === "markdown"
        if (complianceOptions.enableConflictDetection !== undefined) {
          requestBody.detection_mode = complianceOptions.conflictDetectionMode || "both"
        }
      } else if (isGenerationFlow) {
        if (generationOptions?.jurisdiction) {
          requestBody.jurisdiction = generationOptions.jurisdiction
          requestBody.jurisdictions = [generationOptions.jurisdiction]
        }
        if (generationOptions?.useRag !== undefined) requestBody.use_rag = generationOptions.useRag
        requestBody.additional_context = currentFileContent || userMessage.content
      }

      const response = await fetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("响应体不可读取")
      const decoder = new TextDecoder()
      let assistantContent = ""
      let bufferedChunk = ""
      setIsThinking(false)

      const updateAssistantMessage = (content: string) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessageId ? { ...message, content } : message,
          ),
        )
      }

      const processSseLine = (rawLine: string) => {
        const line = rawLine.trimEnd()
        if (!line.startsWith("data:")) return

        const data = line.slice(5).trimStart()
        if (!data || data === "[DONE]") return

        try {
          const parsed = JSON.parse(data)
          if (typeof parsed.content !== "string") return
          assistantContent += parsed.content
          updateAssistantMessage(assistantContent)
        } catch {
          return
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        bufferedChunk += decoder.decode(value || new Uint8Array(), { stream: !done })

        const lines = bufferedChunk.split(/\r?\n/)
        bufferedChunk = lines.pop() ?? ""

        for (const line of lines) {
          processSseLine(line)
        }

        if (done) break
      }

      if (bufferedChunk) {
        processSseLine(bufferedChunk)
      }

      updateAssistantMessage(assistantContent)
    } catch (error) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: `处理请求时出错：${error instanceof Error ? error.message : "未知错误"}\n\n请确认后端服务已启动，且接口 ${apiEndpoint} 可访问。`,
              }
            : message,
        ),
      )
    } finally {
      setIsLoading(false)
      setIsThinking(false)
    }
  }

  const handleFileUpload = async (files: FileList) => {
    setIsUploading(true)
    for (const file of Array.from(files)) {
      const allowedTypes = [
        "text/plain",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ]
      if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|pdf|doc|docx)$/i)) {
        alert(`不支持的文件类型：${file.name}`)
        continue
      }
      if (file.size > 10 * 1024 * 1024) {
        alert(`文件过大：${file.name}。当前仅支持 10MB 以内文件。`)
        continue
      }

      try {
        const content =
          file.type === "text/plain"
            ? await file.text()
            : `[文档内容摘要]\n文件名：${file.name}\n文件大小：${formatFileSize(file.size)}\n请基于上传文档继续处理当前任务。`
        const uploadedFile: UploadedFile = {
          id: crypto.randomUUID(),
          name: file.name,
          size: file.size,
          type: file.type,
          content,
          uploadTime: new Date(),
        }
        setUploadedFiles((prev) => [...prev, uploadedFile])
        setCurrentFileContent(content)
        setInput(copy.uploadPrompt.replace("{name}", file.name))
      } catch {
        alert(`文件处理失败：${file.name}`)
      }
    }
    setIsUploading(false)
  }

  const removeFile = (fileId: string) => {
    setUploadedFiles((prev) => {
      const next = prev.filter((file) => file.id !== fileId)
      const removed = prev.find((file) => file.id === fileId)
      if (removed?.content === currentFileContent) setCurrentFileContent(next[next.length - 1]?.content ?? "")
      return next
    })
  }

  const downloadAnswer = (content: string) => {
    if (!content.trim()) return

    const blob = new Blob([content], { type: "text/plain;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `agent_answer_${Date.now()}.txt`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const currentFile = uploadedFiles[uploadedFiles.length - 1]
  const isBackendOnline = backendStatus?.success ?? false
  const statusLabel = isCheckingStatus ? "检测中" : isBackendOnline ? "在线" : "离线"
  const connectionNote = backendStatus?.available_agents?.length
    ? `已发现 ${backendStatus.available_agents.length} 个可用 agent。`
    : "可用状态会自动轮询更新。"
  const statusClassName = isCheckingStatus
    ? "border-slate-200 bg-slate-50 text-slate-600"
    : isBackendOnline
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : "border-amber-200 bg-amber-50 text-amber-700"

  return (
    <section className="mx-auto max-w-[1180px] px-4 sm:px-5 lg:px-6">
      <div className="space-y-5">
        <header className="rounded-[28px] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-3.5">
            <Button asChild variant="ghost" size="sm" className="h-9 rounded-full px-3 text-slate-600 hover:bg-slate-100">
              <Link href={(backLink ?? { href: "/", label: "返回首页" }).href}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                {(backLink ?? { href: "/", label: "返回首页" }).label}
              </Link>
            </Button>
          </div>

          <div className="space-y-4 px-5 py-5">
            <div className="min-w-0 space-y-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <div className={cn("flex h-14 w-14 flex-none items-center justify-center rounded-3xl text-white", color)}>
                  {icon}
                </div>
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {workflowSummary?.badge ? <Badge variant="outline">{workflowSummary.badge}</Badge> : null}
                    <Badge variant="outline">{copy.name}</Badge>
                    {generationOptions?.useRag ? <Badge variant="outline">RAG 已启用</Badge> : null}
                    {complianceOptions?.parallelExecution ? <Badge variant="outline">并行审查</Badge> : null}
                  </div>
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-[2rem]">{title}</h1>
                    <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600 sm:text-[15px]">{description}</p>
                  </div>
                </div>
              </div>

              <AgentInfoDisplay
                agentType={agentType}
                compact
                className="h-fit"
                statusLabel={statusLabel}
                statusClassName={statusClassName}
                statusNote={connectionNote}
                action={
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 rounded-full px-3"
                    onClick={() => void testConnection()}
                    disabled={isTesting}
                  >
                    {isTesting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    测试连接
                  </Button>
                }
              />

            </div>
          </div>
        </header>

        {!isCheckingStatus && !isBackendOnline ? (
          <Alert className="border-amber-200 bg-amber-50 text-amber-900 [&>svg]:text-amber-700">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {backendStatus?.error || "当前未检测到可用后端服务。请先启动后端，再继续发起请求。"}
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
            {workflowSummary ? (
              <SummaryCard title={workflowSummary.title} description={workflowSummary.description} className="h-fit">
                <div className="grid gap-2">
                  {workflowSummary.items.map((item) => (
                    <div key={`${item.label}-${item.value}`} className="rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2.5">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</p>
                      <p className="mt-1.5 text-sm font-medium text-slate-900">{item.value}</p>
                    </div>
                  ))}
                </div>
              </SummaryCard>
            ) : null}

            <SummaryCard title="已上传文件" description="最近上传的文件会优先作为本轮任务的上下文。">
              {uploadedFiles.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-4 text-sm leading-6 text-slate-500">
                  还没有上传材料。你可以直接提问，也可以先补充政策正文、需求说明或旧版文档。
                </div>
              ) : (
                <div className="space-y-3">
                  {uploadedFiles.map((file) => (
                    <div key={file.id} className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{formatFileSize(file.size)} · {formatTime(file.uploadTime)}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeFile(file.id)}
                          className="rounded-full p-1 text-slate-400 transition hover:bg-white hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                          aria-label={`移除 ${file.name}`}
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </SummaryCard>
          </aside>

          <Card className="overflow-hidden border-slate-200 bg-white shadow-sm">
            <CardContent className="p-0">
              <div className="border-b border-slate-200 px-6 py-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">对话</p>
                    <h2 className="mt-2 text-xl font-semibold text-slate-950">对话区</h2>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{currentFile ? `当前附件：${currentFile.name}` : "当前附件：无"}</Badge>
                    <Badge variant="outline">{messages.length} 条消息</Badge>
                  </div>
                </div>
              </div>

              <div ref={messageContainerRef} className="min-h-[480px] max-h-[calc(100vh-20rem)] overflow-y-auto px-6 py-6">
                {messages.length === 0 ? (
                  <div className="flex min-h-[420px] flex-col justify-center">
                    <div className="mx-auto max-w-3xl text-center">
                      <Badge variant="outline">从这里开始</Badge>
                      <h3 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">{copy.emptyTitle}</h3>
                      <p className="mt-3 text-sm leading-7 text-slate-500 sm:text-[15px]">{copy.emptyHint}</p>
                    </div>
                    <div className="mt-8 grid gap-4 lg:grid-cols-3">
                      <div className="rounded-3xl border border-slate-200 bg-white p-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
                          <FileText className="h-5 w-5" />
                        </div>
                        <p className="mt-4 text-sm font-semibold text-slate-950">上传材料</p>
                        <p className="mt-2 text-sm leading-6 text-slate-500">支持 TXT、PDF、DOC、DOCX，最近上传文件会自动进入上下文。</p>
                      </div>
                      <div className="rounded-3xl border border-slate-200 bg-white p-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
                          <User className="h-5 w-5" />
                        </div>
                        <p className="mt-4 text-sm font-semibold text-slate-950">补充任务说明</p>
                        <p className="mt-2 text-sm leading-6 text-slate-500">说明产品类型、目标法域、处理目的和希望的输出方式。</p>
                      </div>
                      <div className="rounded-3xl border border-slate-200 bg-white p-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
                          <Bot className="h-5 w-5" />
                        </div>
                        <p className="mt-4 text-sm font-semibold text-slate-950">接收结构化结果</p>
                        <p className="mt-2 text-sm leading-6 text-slate-500">结果会在此流式返回，你可以继续追问、细化或导出文本。</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {messages.map((message) => {
                      if (message.role === "assistant" && !message.content.trim() && (isLoading || isThinking)) return null
                      const isAssistant = message.role === "assistant"
                      return (
                        <div key={message.id} className={cn("flex gap-3", isAssistant ? "justify-start" : "justify-end")}>
                          {isAssistant ? (
                            <div className="flex h-10 w-10 flex-none items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                              <Bot className="h-5 w-5" />
                            </div>
                          ) : null}
                          <div className={cn("max-w-3xl rounded-[28px] border px-5 py-4 shadow-sm", isAssistant ? "border-slate-200 bg-white text-slate-800" : "border-slate-950 bg-slate-950 text-white")}>
                            <div className="flex items-center justify-between gap-4">
                              <div className={cn("flex items-center gap-2 text-xs", isAssistant ? "text-slate-400" : "text-slate-300")}>
                                {isAssistant ? <CheckCircle2 className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
                                <span>{isAssistant ? "助手" : "你"}</span>
                                <span>·</span>
                                <span>{formatTime(message.timestamp)}</span>
                              </div>
                              {isAssistant ? (
                                <Button type="button" variant="ghost" size="sm" onClick={() => downloadAnswer(message.content)} className="h-8 rounded-full px-3 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-900">
                                  导出
                                </Button>
                              ) : null}
                            </div>
                            <div className={cn("mt-3 break-words text-sm leading-7", isAssistant ? "text-slate-700" : "text-slate-100")}>
                              {isAssistant ? (
                                <MarkdownRenderer content={message.content} />
                              ) : (
                                <p className="whitespace-pre-wrap">{message.content}</p>
                              )}
                            </div>
                          </div>
                          {!isAssistant ? (
                            <div className="flex h-10 w-10 flex-none items-center justify-center rounded-2xl bg-slate-950 text-white">
                              <User className="h-5 w-5" />
                            </div>
                          ) : null}
                        </div>
                      )
                    })}
                    {isLoading || isThinking ? (
                      <div className="flex gap-3">
                        <div className="flex h-10 w-10 flex-none items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                          {isThinking ? <Brain className="h-5 w-5 animate-pulse" /> : <Bot className="h-5 w-5" />}
                        </div>
                        <div className="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm">
                          <div className="flex items-center gap-3 text-sm text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span>{isThinking ? "正在组织上下文..." : "正在处理请求..."}</span>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              <form onSubmit={(event) => void handleSubmit(event)} className="border-t border-slate-200 bg-white px-6 py-5">
                {currentFile ? (
                  <div className="mb-3 flex flex-wrap gap-2">
                    <Badge variant="outline">已载入：{currentFile.name}</Badge>
                    <Badge variant="outline">{formatFileSize(currentFile.size)}</Badge>
                  </div>
                ) : null}
                <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-3">
                  <Textarea
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault()
                        void handleSubmit(event)
                      }
                    }}
                    placeholder={placeholder}
                    disabled={isLoading}
                    className="min-h-[132px] resize-none border-0 bg-transparent px-2 py-2 text-sm leading-7 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                  <div className="mt-3 flex flex-col gap-3 border-t border-slate-200 pt-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap items-center gap-2">
                      <FileUploadButton onFileUpload={handleFileUpload} isUploading={isUploading} disabled={isLoading} className="w-fit" />
                      <Badge variant="outline">Enter 发送</Badge>
                      <Badge variant="outline">Shift + Enter 换行</Badge>
                    </div>
                    <Button type="submit" disabled={isLoading || (!input.trim() && !currentFileContent)} className="rounded-xl bg-slate-950 px-5 text-white hover:bg-slate-800">
                      {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                      {isLoading ? "正在处理..." : "提交请求"}
                    </Button>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  )
}
