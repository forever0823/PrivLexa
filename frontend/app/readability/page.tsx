import { Eye } from "lucide-react"

import ChatInterface from "@/components/chat-interface"

export default function ReadabilityPage() {
  return (
    <ChatInterface
      title="可读性优化"
      description="分析隐私政策中的句式、术语和结构，让文本更容易被普通用户快速理解。"
      placeholder="粘贴隐私政策文本，或上传文档进行分析。我会指出表达复杂、术语堆叠和结构不清晰的部分。"
      icon={<Eye className="h-6 w-6 text-white" />}
      color="bg-violet-600"
      apiEndpoint="http://127.0.0.1:8001/chat"
      agentType="readability_checker"
    />
  )
}
