import type { NextRequest } from "next/server"

import { createSseTextResponse } from "@/lib/api-utils"

export const maxDuration = 30

interface ReadabilityRequest {
  agent_type: string
  message: string
  context?: Record<string, any>
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    const readabilityRequest: ReadabilityRequest = {
      agent_type: "readability_checker",
      message: body.fileContent || body.text || body.message || "请分析这个隐私政策的可读性，并给出可读性优化建议",
      context: {
        text: body.fileContent || body.text || body.message,
        target_audience: body.target_audience || "普通用户",
        check_dimensions: body.check_dimensions || [
          "语言复杂度",
          "句子长度",
          "专业术语",
          "结构清晰度",
          "信息组织",
          "用户友好性",
        ],
        file_content: body.fileContent,
        uploaded_files: body.uploaded_files || [],
      },
    }

    // 调用后端可读性检测API
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"
    const response = await fetch(`${backendUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
      body: JSON.stringify(readabilityRequest),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || errorData.error_message || errorData.message || `后端 API 错误: ${response.status}`
      )
    }

    const data = await response.json()

    if (!data.success) {
      throw new Error(data.error_message || data.error || data.message || "可读性检测失败")
    }

    return createSseTextResponse(data.response || "", {}, 400)
  } catch (error) {
    console.error("可读性检测接口错误:", error)
    return new Response(
      JSON.stringify({
        success: false,
        error_message: error instanceof Error ? error.message : "检测失败: 内部服务错误",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    )
  }
}
