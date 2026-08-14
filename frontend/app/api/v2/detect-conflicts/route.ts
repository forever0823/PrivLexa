import type { NextRequest } from "next/server"
import type {
  ConflictDetectionRequest,
  ConflictDetectionResponse,
} from "@/lib/api-models"
import { createSseTextResponse } from "@/lib/api-utils"

export const maxDuration = 45

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const rawDetectionMode = body.detection_mode || body.conflictDetectionMode || "both"
    const detectionMode =
      rawDetectionMode === "hard" || rawDetectionMode === "soft" || rawDetectionMode === "both"
        ? rawDetectionMode
        : "both"

    const conflictDetectionRequest: ConflictDetectionRequest = {
      policy_text: body.policy_text || body.fileContent || body.privacy_policy || body.message,
      jurisdiction: body.jurisdiction || "CN",
      detection_types: body.detection_types || ["hard", "soft"],
      detection_mode: detectionMode,
      include_suggestions: body.include_suggestions !== false,
    }

    if (!conflictDetectionRequest.policy_text) {
      throw new Error("缺少必需参数: policy_text")
    }

    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"
    const response = await fetch(`${backendUrl}/api/v2/detect-conflicts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
      body: JSON.stringify(conflictDetectionRequest),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.message || `后端 API 错误: ${response.status}`)
    }

    const data: ConflictDetectionResponse = await response.json()

    if (!data.success) {
      throw new Error(data.error_message || "冲突检测失败")
    }

    return createSseTextResponse(
      data.detection_results || "",
      {
        hard_conflicts: data.hard_conflicts,
        soft_conflicts: data.soft_conflicts,
        total_conflicts: data.total_conflicts,
        critical_count: data.critical_count,
        major_count: data.major_count,
        minor_count: data.minor_count,
        detection_mode: data.detection_mode,
      },
      500,
    )
  } catch (error) {
    console.error("冲突检测接口错误:", error)
    return new Response(
      JSON.stringify({
        success: false,
        error_message: error instanceof Error ? error.message : "内部服务错误",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    )
  }
}
