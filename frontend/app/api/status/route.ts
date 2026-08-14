import type { NextRequest } from "next/server"

export async function GET(req: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001"

    // 1) 优先调用 /health（FastAPI 推荐）
    // 2) 若 404 /health，则尝试根路径 /
    // 3) 若依旧 404，则继续后续流程，但标记 backend_info = null
    let backendInfo: any = null
    let rootOk = false

    // helper
    const safeFetch = async (url: string) => {
      try {
        const res = await fetch(url, {
          headers: {
            ...(process.env.BACKEND_API_KEY && {
              Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
            }),
          },
        })
        return res
      } catch {
        return undefined
      }
    }

    // 先试 /health
    let res = await safeFetch(`${backendUrl.replace(/\/$/, "")}/health`)
    if (res && res.ok) {
      rootOk = true
      backendInfo = await res.json().catch(() => null)
    } else {
      // 再试 /
      res = await safeFetch(`${backendUrl.replace(/\/$/, "")}/`)
      if (res && res.ok) {
        rootOk = true
        backendInfo = await res.json().catch(() => null)
      }
    }

    if (!rootOk) {
      // 如果仍失败，不抛错，继续返回 disconnected 状态（便于前端 UI 处理）
      return Response.json(
        {
          success: false,
          backend_status: "disconnected",
          error: "无法连接到后端 /health 或根路径",
          timestamp: new Date().toISOString(),
        },
        { status: 200 },
      )
    }

    // 尝试获取Agent列表（如果后端支持）
    let agentData = null
    try {
      const agentResponse = await fetch(`${backendUrl}/agents`, {
        method: "GET",
        headers: {
          ...(process.env.BACKEND_API_KEY && {
            Authorization: `Bearer ${process.env.BACKEND_API_KEY}`,
          }),
        },
      })

      if (agentResponse.ok) {
        agentData = await agentResponse.json()
      }
    } catch (error) {
      // Agent端点可能不存在，忽略错误
      console.log("Agent 端点不可用:", error)
    }

    return Response.json({
      success: true,
      backend_status: "connected",
      backend_info: backendInfo,
      agents: agentData,
      available_agents: [
        { name: "隐私政策生成专家", type: "privacy_policy_generator", status: "active" },
        { name: "合规性检测专家", type: "compliance_checker", status: "active" },
      ],
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error("状态接口错误:", error)
    return Response.json(
      {
        success: false,
        backend_status: "disconnected",
        error: error instanceof Error ? error.message : "未知错误",
        timestamp: new Date().toISOString(),
      },
      { status: 500 },
    )
  }
}
