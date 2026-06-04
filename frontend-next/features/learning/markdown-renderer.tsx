import { marked } from "marked"

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
  const html = marked.parse(content || "", {
    async: false
  })

  return (
    <article
      className={cn("markdown-body max-w-none text-sm leading-7", className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
