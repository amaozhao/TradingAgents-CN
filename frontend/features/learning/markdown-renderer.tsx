import { marked, type Token, type Tokens } from "marked"

import { MermaidRenderer } from "@/features/learning/mermaid-renderer"
import { cn } from "@/libs/utils"

interface MarkdownRendererProps {
  content: string
  className?: string
}

marked.use({
  gfm: true,
  breaks: true
})

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  const parts = splitMarkdownParts(content || "")

  return (
    <article className={cn("markdown-body max-w-none text-sm leading-7", className)}>
      {parts.map((part, index) => {
        if (part.type === "mermaid") {
          return <MermaidRenderer key={index} chart={part.chart} className="my-4" />
        }

        return (
          <div
            key={index}
            dangerouslySetInnerHTML={{ __html: parseMarkdown(part.markdown) }}
          />
        )
      })}
    </article>
  )
}

type MarkdownPart =
  | { type: "markdown"; markdown: string }
  | { type: "mermaid"; chart: string }

function splitMarkdownParts(content: string): MarkdownPart[] {
  const tokens = marked.lexer(content)
  const parts: MarkdownPart[] = []
  let markdown = ""

  for (const token of tokens) {
    if (isMermaidCodeToken(token)) {
      if (markdown) {
        parts.push({ type: "markdown", markdown })
        markdown = ""
      }
      parts.push({ type: "mermaid", chart: token.text })
    } else {
      markdown += token.raw
    }
  }

  if (markdown) {
    parts.push({ type: "markdown", markdown })
  }

  return parts
}

function isMermaidCodeToken(token: Token): token is Tokens.Code {
  return token.type === "code" && normalizeLanguage(token.lang) === "mermaid"
}

function normalizeLanguage(language?: string) {
  return language?.trim().split(/\s+/)[0]?.toLowerCase()
}

function parseMarkdown(markdown: string) {
  return marked.parse(markdown, {
    async: false
  })
}
