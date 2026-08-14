import { Children, isValidElement, type ComponentPropsWithoutRef, type ReactNode } from "react"
import ReactMarkdown, { defaultUrlTransform, type Components, type UrlTransform } from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"

const EXTERNAL_LINK_PATTERN = /^(?:https?:)?\/\//i
const FENCE_PATTERN = /^(```+|~~~+)/
const MARKDOWN_BLOCK_PATTERN =
  /^(?:#{1,6}\s|>\s?|[-*+]\s|\d+\.\s|```|~~~| {0,3}(?:[-*_]){3,}\s*$|\|.*\||\[\^.+\]:)/
const ZERO_WIDTH_PATTERN = /[\u200B-\u200D\uFEFF]/g

type HeadingTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6"
type HeadingRendererProps = ComponentPropsWithoutRef<"h1"> & { children?: ReactNode; node?: unknown }

function isMarkdownBlock(line: string) {
  return MARKDOWN_BLOCK_PATTERN.test(line.trim())
}

function normalizeMarkdownContent(content: string) {
  const normalized = content.replace(/\r\n?/g, "\n").replace(ZERO_WIDTH_PATTERN, "").trim()
  if (!normalized) return normalized

  const lines = normalized.split("\n")
  const result: string[] = []
  let inFence = false
  let prevBlank = false

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] ?? ""
    const trimmed = line.trim()

    if (FENCE_PATTERN.test(trimmed)) {
      inFence = !inFence
      result.push(line.replace(/\s+$/g, ""))
      prevBlank = false
      continue
    }

    if (inFence) {
      result.push(line)
      prevBlank = false
      continue
    }

    // Collapse consecutive blank lines into one
    if (!trimmed) {
      if (!prevBlank) {
        result.push("")
      }
      prevBlank = true
      continue
    }

    prevBlank = false

    const nextLine = lines[index + 1]
    const nextTrimmed = nextLine?.trim() ?? ""
    const shouldForceBreak =
      nextTrimmed.length > 0 &&
      !isMarkdownBlock(trimmed) &&
      !isMarkdownBlock(nextTrimmed) &&
      !/(?: {2,}|\\)$/.test(line)

    result.push(shouldForceBreak ? `${line.replace(/\s+$/g, "")}  ` : line)
  }

  return result.join("\n")
}

function getTextContent(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number") return String(child)
      if (!isValidElement(child)) return ""

      const props = child.props as { children?: ReactNode }
      return getTextContent(props.children)
    })
    .join("")
    .trim()
}

function slugifyHeading(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^\p{Letter}\p{Number}\s-]/gu, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
}

function createHeadingIdResolver() {
  const headingCounts = new Map<string, number>()

  return (children: ReactNode) => {
    const base = slugifyHeading(getTextContent(children)) || "section"
    const count = (headingCounts.get(base) ?? 0) + 1
    headingCounts.set(base, count)
    return count === 1 ? base : `${base}-${count}`
  }
}

function createHeadingRenderer(tag: HeadingTag, resolveHeadingId: (children: ReactNode) => string) {
  return function HeadingRenderer({ children, node: _node, ...props }: HeadingRendererProps) {
    const Tag = tag
    const id = resolveHeadingId(children)

    return (
      <Tag {...props} id={id}>
        {children}
        <a
          href={`#${id}`}
          aria-label={`Jump to ${getTextContent(children) || "section"}`}
          className="markdown-heading-link"
        >
          #
        </a>
      </Tag>
    )
  }
}

function shouldOpenInNewTab(href: string) {
  return EXTERNAL_LINK_PATTERN.test(href)
}

function getCodeBlockLanguage(children: ReactNode) {
  const [firstChild] = Children.toArray(children)
  if (!firstChild || !isValidElement(firstChild)) return null

  const props = firstChild.props as { className?: string }
  const match = props.className?.match(/language-([^\s]+)/)
  return match?.[1]?.replace(/[-_]+/g, " ") ?? null
}

const safeUrlTransform: UrlTransform = (url) => defaultUrlTransform(url)

function createMarkdownComponents(): Components {
  const resolveHeadingId = createHeadingIdResolver()

  return {
    a: ({ children, href, node: _node, ...props }) => {
      const safeHref = href || undefined
      const external = safeHref ? shouldOpenInNewTab(safeHref) : false

      return (
        <a
          {...props}
          href={safeHref}
          target={external ? "_blank" : undefined}
          rel={external ? "noopener noreferrer nofollow" : undefined}
        >
          {children}
        </a>
      )
    },
    h1: createHeadingRenderer("h1", resolveHeadingId),
    h2: createHeadingRenderer("h2", resolveHeadingId),
    h3: createHeadingRenderer("h3", resolveHeadingId),
    h4: createHeadingRenderer("h4", resolveHeadingId),
    h5: createHeadingRenderer("h5", resolveHeadingId),
    h6: createHeadingRenderer("h6", resolveHeadingId),
    img: ({ alt, node: _node, src, ...props }) => {
      if (!src) return null
      return <img {...props} src={src} alt={alt || ""} loading="lazy" decoding="async" />
    },
    input: ({ checked, className, disabled, node: _node, type, ...props }) => {
      if (type !== "checkbox") {
        return <input {...props} type={type} className={className} disabled={disabled} />
      }

      return (
        <input
          {...props}
          checked={Boolean(checked)}
          className={cn("markdown-task-checkbox", className)}
          disabled
          readOnly
          type="checkbox"
        />
      )
    },
    pre: ({ children, className, node: _node, ...props }) => {
      const language = getCodeBlockLanguage(children)

      return (
        <div className="markdown-code-block">
          {language ? (
            <div className="markdown-code-header">
              <span>{language}</span>
            </div>
          ) : null}
          <pre {...props} className={cn(className, "markdown-pre")}>
            {children}
          </pre>
        </div>
      )
    },
    table: ({ children, node: _node, ...props }) => (
      <div className="markdown-table-wrapper">
        <table {...props}>{children}</table>
      </div>
    ),
  }
}

interface MarkdownRendererProps {
  content: string
  className?: string
}

export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  const normalizedContent = normalizeMarkdownContent(content)
  if (!normalizedContent) return null

  return (
    <div className={cn("markdown-content", className)}>
      <ReactMarkdown
        components={createMarkdownComponents()}
        remarkPlugins={[remarkGfm]}
        skipHtml
        urlTransform={safeUrlTransform}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  )
}
