import type { NextRequest } from "next/server"

import { createSseTextResponse } from "@/lib/api-utils"

export const maxDuration = 30

interface ChatRequest {
  agent_type: string
  message: string
  context?: Record<string, any>
}

interface BackendResponse {
  success: boolean
  response?: string
  error?: string
  agent_type?: string
  message?: string
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    const chatRequest: ChatRequest = {
      agent_type: body.agent_type || "privacy_policy_generator",
      message: body.message || "",
      context: {
        ...body.context,
        file_content: body.fileContent,
        uploaded_files: body.uploaded_files || [],
      },
    }

    // 调用后端API
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"
    const response = await fetch(`${backendUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
      body: JSON.stringify(chatRequest),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.message || `后端 API 错误: ${response.status}`)
    }

    const data: BackendResponse = await response.json()

    if (!data.success) {
      throw new Error(data.error || data.message || "后端处理失败")
    }

    return createSseTextResponse(data.response || "", {}, 400)
  } catch (error) {
    console.error("聊天接口错误:", error)
    return new Response(
      JSON.stringify({
        success: false,
        error: error instanceof Error ? error.message : "内部服务器错误",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    )
  }
}
