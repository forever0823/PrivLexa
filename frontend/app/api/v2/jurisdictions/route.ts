import type { NextRequest } from "next/server"
import type { ListJurisdictionsResponse } from "@/lib/api-models"

export const maxDuration = 10

export async function GET(req: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"

    // 调用后端的 v2 API 获取法域列表
    const response = await fetch(`${backendUrl}/api/v2/jurisdictions`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(
        errorData.detail || errorData.message || `后端 API 错误: ${response.status}`
      )
    }

    const data: ListJurisdictionsResponse = await response.json()

    return Response.json(data)
  } catch (error) {
    console.error("法域列表接口错误:", error)
    return Response.json(
      {
        success: false,
        error_message: error instanceof Error ? error.message : "获取法域列表失败",
        // 提供备选法域列表
        jurisdictions: [
          {
            code: "CN",
            name: "中国",
            description: "遵循《个人信息保护法》(PIPL)",
          },
          {
            code: "US",
            name: "美国",
            description: "遵循 CCPA, COPPA 等法规",
          },
          {
            code: "EU",
            name: "欧盟",
            description: "遵循《通用数据保护条例》(GDPR)",
          },
          {
            code: "JP",
            name: "日本",
            description: "遵循《个人信息保护法》(APPI)",
          },
          {
            code: "SG",
            name: "新加坡",
            description: "遵循《个人数据保护法》(PDPA)",
          },
          {
            code: "GLOBAL",
            name: "全球",
            description: "综合多个地区的法规",
          },
        ],
      },
      { status: 200 }
    )
  }
}
