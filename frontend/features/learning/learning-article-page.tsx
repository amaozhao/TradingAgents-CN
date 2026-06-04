import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import { MarkdownRenderer } from "@/features/learning/markdown-renderer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getArticle, learningArticles, readArticleMarkdown } from "@/features/learning/content"

export async function LearningArticlePage({ articleId }: { articleId: string }) {
  const article = getArticle(articleId)
  if (!article) notFound()
  if (article.externalUrl) redirect(article.externalUrl)

  const markdown = await readArticleMarkdown(article)
  const index = learningArticles.findIndex((item) => item.id === article.id)
  const previous = index > 0 ? learningArticles[index - 1] : null
  const next = index >= 0 && index < learningArticles.length - 1 ? learningArticles[index + 1] : null

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge>{article.categoryTitle}</Badge>
            <Badge variant="secondary">{article.difficulty}</Badge>
            <span className="text-sm text-muted-foreground">{article.readTime}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-normal">{article.title}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{article.description}</p>
        </div>
        <Button variant="outline" asChild><Link href={`/learning/${article.category}`}>返回分类</Link></Button>
      </div>
      <MarkdownRenderer content={markdown} className="rounded-md border bg-background p-6" />
      <div className="mt-6 flex flex-wrap justify-between gap-3">
        {previous ? <Button variant="outline" asChild><Link href={`/learning/article/${previous.id}`}>上一篇：{previous.title}</Link></Button> : <span />}
        {next ? <Button variant="outline" asChild><Link href={`/learning/article/${next.id}`}>下一篇：{next.title}</Link></Button> : null}
      </div>
    </div>
  )
}
