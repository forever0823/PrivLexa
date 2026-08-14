import type { NextRequest } from "next/server"
import type {
  GeneratePolicyRequest,
  GeneratePolicyResponse,
} from "@/lib/api-models"
import { createSseTextResponse } from "@/lib/api-utils"

export const maxDuration = 30

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    // 构建符合后端 v2 API 的请求
    const generatePolicyRequest: GeneratePolicyRequest = {
      jurisdiction: body.jurisdiction || "CN",
      app_name: body.app_name,
      app_type: body.app_type,
      data_types: body.data_types,
      regions: body.regions,
      use_rag: body.use_rag !== false, // 默认启用 RAG
      use_fine_tuned_glm: body.use_fine_tuned_glm === true, // 默认禁用
      additional_context: body.additional_context,
    }

    // 验证必需字段
    if (!generatePolicyRequest.app_name) {
      throw new Error("缺少必需参数: app_name")
    }
    if (!generatePolicyRequest.app_type) {
      throw new Error("缺少必需参数: app_type")
    }
    if (!generatePolicyRequest.data_types || generatePolicyRequest.data_types.length === 0) {
      throw new Error("缺少必需参数: data_types")
    }

    // 调用后端的 v2 API
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"
    const response = await fetch(`${backendUrl}/api/v2/generate-policy`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
      body: JSON.stringify(generatePolicyRequest),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || errorData.message || `后端 API 错误: ${response.status}`
      )
    }

    const data: GeneratePolicyResponse = await response.json()

    if (!data.success) {
      throw new Error(data.error_message || "隐私政策生成失败")
    }

    return createSseTextResponse(
      data.policy || "",
      {
        jurisdiction: data.jurisdiction,
        metadata: data.metadata,
      },
      600,
    )
  } catch (error) {
    console.error("隐私政策生成接口错误:", error)
    return new Response(
      JSON.stringify({
        success: false,
        error_message: error instanceof Error ? error.message : "生成失败: 内部服务错误",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    )
  }
}
