"use client"

import type React from "react"

import { useState } from "react"
import { FileText, Upload } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface FileUploadButtonProps {
  onFileUpload: (files: FileList) => void
  isUploading: boolean
  disabled?: boolean
  className?: string
  variant?: "default" | "outline" | "ghost"
  size?: "sm" | "default" | "lg"
}

export default function FileUploadButton({
  onFileUpload,
  isUploading,
  disabled = false,
  className,
  variant = "outline",
  size = "sm",
}: FileUploadButtonProps) {
  const [dragOver, setDragOver] = useState(false)

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (files && files.length > 0) {
      onFileUpload(files)
    }
    event.target.value = ""
  }

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setDragOver(true)
  }

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setDragOver(false)
  }

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    setDragOver(false)

    const files = event.dataTransfer.files
    if (files && files.length > 0) {
      onFileUpload(files)
    }
  }

  return (
    <div
      className={cn("relative", dragOver && "rounded-xl ring-2 ring-sky-400 ring-offset-2", className)}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <Button
        variant={variant}
        size={size}
        disabled={disabled || isUploading}
        className={cn(
          "relative overflow-hidden rounded-xl transition-all duration-200",
          dragOver && "border-sky-300 bg-sky-50 text-sky-700",
          isUploading && "cursor-not-allowed",
        )}
        asChild
      >
        <label className="flex cursor-pointer items-center gap-2">
          {isUploading ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              <span className="text-xs font-medium">上传中...</span>
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              <span className="text-xs font-medium">上传材料</span>
            </>
          )}
          <input
            type="file"
            multiple
            accept=".txt,.pdf,.doc,.docx"
            onChange={handleFileChange}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            disabled={disabled || isUploading}
          />
        </label>
      </Button>

      {dragOver ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl bg-sky-50/95">
          <div className="flex items-center gap-1 text-xs font-medium text-sky-700">
            <FileText className="h-4 w-4" />
            松开以上传文件
          </div>
        </div>
      ) : null}
    </div>
  )
}
