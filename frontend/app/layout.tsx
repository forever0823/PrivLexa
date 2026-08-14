import type { Metadata } from "next"

import "./globals.css"

export const metadata: Metadata = {
  title: "PrivLexa · 隐律智策",
  description: "面向多法域隐私政策生成与合规检测的智能工作台。",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
