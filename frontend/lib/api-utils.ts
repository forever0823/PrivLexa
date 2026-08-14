export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export function createApiResponse<T>(success: boolean, data?: T, error?: string, message?: string): ApiResponse<T> {
  return {
    success,
    data,
    error,
    message,
  }
}

export function handleApiError(error: unknown): Response {
  console.error("API 错误:", error)

  if (error instanceof Error) {
    return Response.json(createApiResponse(false, null, error.message), { status: 500 })
  }

  return Response.json(createApiResponse(false, null, "内部服务器错误"), { status: 500 })
}

export async function validateRequest(req: Request) {
  try {
    const body = await req.json()

    if (!body.messages || !Array.isArray(body.messages)) {
      throw new Error("messages 格式无效")
    }

    return body
  } catch (error) {
    throw new Error("请求体格式无效")
  }
}

export function createSseTextResponse(
  text: string,
  extraPayload: Record<string, unknown> = {},
  chunkSize = 400,
): Response {
  const encoder = new TextEncoder()
  const safeText = text || ""
  const safeChunkSize = Math.max(1, chunkSize)

  const stream = new ReadableStream({
    start(controller) {
      for (let index = 0; index < safeText.length; index += safeChunkSize) {
        const content = safeText.slice(index, index + safeChunkSize)
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ ...extraPayload, content })}\n\n`))
      }

      controller.enqueue(encoder.encode("data: [DONE]\n\n"))
      controller.close()
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  })
}
