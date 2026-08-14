import type { NextRequest } from "next/server"

import type { GeneratePolicyRequest } from "@/lib/api-models"
import { createSseTextResponse } from "@/lib/api-utils"

export const maxDuration = 30

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const selectedJurisdiction =
      body.jurisdiction || body.context?.generation_options?.jurisdiction || body.jurisdictions?.[0] || "CN"
    const useRag = body.use_rag ?? body.context?.generation_options?.useRag ?? true

    const generatePolicyRequest: GeneratePolicyRequest = {
      jurisdiction: selectedJurisdiction,
      app_name: body.app_name || extractAppName(body.message) || "用户应用",
      app_type: body.app_type || extractAppType(body.message) || "通用应用",
      data_types: body.data_types || extractDataTypes(body.message) || ["用户信息", "设备信息"],
      regions: body.regions || mapJurisdictionToRegions(selectedJurisdiction) || extractRegions(body.message) || ["中国"],
      use_rag: useRag,
      use_fine_tuned_glm: body.use_fine_tuned_glm === true,
      additional_context: body.additional_context || body.fileContent || body.message,
    }

    if (!generatePolicyRequest.app_name) {
      throw new Error("缺少必需参数: app_name")
    }
    if (!generatePolicyRequest.app_type) {
      throw new Error("缺少必需参数: app_type")
    }
    if (!generatePolicyRequest.data_types || generatePolicyRequest.data_types.length === 0) {
      throw new Error("缺少必需参数: data_types")
    }

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
        errorData.detail || errorData.error_message || errorData.message || `后端 API 错误: ${response.status}`,
      )
    }

    const data = await response.json()

    if (!data.success) {
      throw new Error(data.error_message || data.error || data.message || "隐私政策生成失败")
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
      },
    )
  }
}

function extractAppName(message: string): string | null {
  const match = message.match(/应用名(?:称)?[:：]?\s*([^\s，。]+)/i)
  return match ? match[1] : null
}

function extractAppType(message: string): string | null {
  const types = ["社交", "电商", "工具", "游戏", "教育", "医疗", "金融", "新闻"]
  for (const type of types) {
    if (message.includes(type)) {
      return `${type}应用`
    }
  }
  return null
}

function extractDataTypes(message: string): string[] | null {
  const dataTypes: string[] = []
  const typeMap = {
    用户信息: ["用户", "个人", "姓名", "邮箱", "手机"],
    设备信息: ["设备", "硬件", "系统"],
    位置信息: ["位置", "地理", "GPS", "定位"],
    使用数据: ["使用", "行为", "操作", "点击"],
  }

  for (const [type, keywords] of Object.entries(typeMap)) {
    if (keywords.some((keyword) => message.includes(keyword))) {
      dataTypes.push(type)
    }
  }

  return dataTypes.length > 0 ? dataTypes : null
}

function extractRegions(message: string): string[] | null {
  const regions: string[] = []
  const regionMap = {
    中国: ["中国", "国内", "大陆"],
    欧盟: ["欧盟", "欧洲", "EU", "GDPR"],
    美国: ["美国", "美利坚", "US", "USA"],
    全球: ["全球", "国际", "worldwide"],
  }

  for (const [region, keywords] of Object.entries(regionMap)) {
    if (keywords.some((keyword) => message.includes(keyword))) {
      regions.push(region)
    }
  }

  return regions.length > 0 ? regions : null
}

function mapJurisdictionToRegions(jurisdiction: string): string[] | null {
  const regionMap: Record<string, string[]> = {
    CN: ["中国"],
    US: ["美国"],
    EU: ["欧盟"],
    GLOBAL: ["全球"],
  }

  return regionMap[jurisdiction] || null
}
