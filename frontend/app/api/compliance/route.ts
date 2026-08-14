import type { NextRequest } from "next/server"
import type { ComplianceCheckRequest } from "@/lib/api-models"
import { createSseTextResponse } from "@/lib/api-utils"

export const maxDuration = 60 // 合规检测可能耗时

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    // 构建符合后端 v2 API 的请求
    const complianceCheckRequest: ComplianceCheckRequest = {
      policy_text: body.fileContent || body.privacy_policy || body.message,
      privacy_policy: body.fileContent || body.privacy_policy || body.message,
      policy_title: body.policy_title,
      target_regions: body.target_regions || ["中国", "欧盟", "美国"],
      check_points: body.check_points || [
        "数据收集合法性",
        "用户权利说明",
        "数据处理目的",
        "第三方共享",
        "数据安全措施",
        "跨境传输",
        "数据保留期限",
        "联系方式",
      ],
      jurisdictions: body.jurisdictions || ["CN"],
      parallel_execution: body.parallel_execution !== false,
      return_markdown: body.return_markdown !== false,
      enable_conflict_detection: body.enable_conflict_detection === true,
      detection_mode: body.detection_mode || "both",
    }

    // 验证必需字段
    if (!complianceCheckRequest.policy_text && !complianceCheckRequest.privacy_policy) {
      throw new Error("缺少必需参数: policy_text 或 privacy_policy")
    }

    // 调用后端合规检测 v2 API
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"
    const response = await fetch(`${backendUrl}/api/v2/compliance-check`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
      body: JSON.stringify(complianceCheckRequest),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || errorData.error_message || errorData.message || `后端 API 错误: ${response.status}`
      )
    }

    const data = await response.json()

    if (!data.success) {
      throw new Error(data.error_message || data.error || data.message || "合规性检测失败")
    }

    return createSseTextResponse(
      data.markdown_report || data.compliance_report || "",
      {
        jurisdiction_results: data.jurisdiction_results,
        overall_status: data.overall_status,
        overall_score: data.overall_score,
        report_format: data.report_format,
      },
      600,
    )
  } catch (error) {
    console.error("合规检测接口错误:", error)
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
