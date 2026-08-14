import type { NextRequest } from "next/server"

export async function POST(req: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"

    // 测试后端的 health 端点（非流式）
    const response = await fetch(`${backendUrl}/health`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
        }),
      },
    })

    if (!response.ok) {
      throw new Error(`后端健康检查失败: ${response.status}`)
    }

    const data = await response.json()

    return Response.json({
      success: true,
      message: "连接测试成功",
      backend_status: data.status,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error("连接测试接口错误:", error)
    return Response.json(
      {
        success: false,
        message: "连接测试失败",
        error: error instanceof Error ? error.message : "未知错误",
        timestamp: new Date().toISOString(),
      },
      { status: 500 },
    )
  }
}
