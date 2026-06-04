import Link from "next/link"
import { notFound } from "next/navigation"

import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { getArticlesByCategory, getCategory } from "@/features/learning/content"

export function LearningCategoryPage({ categoryId }: { categoryId: string }) {
  const category = getCategory(categoryId)
  if (!category) notFound()
  const articles = getArticlesByCategory(categoryId)

  return (
    <div>
      <PageHeader title={category.title} description={category.description} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {articles.map((article) => (
          <Link key={article.id} href={`/learning/article/${article.id}`} className="rounded-md border bg-background p-5 transition-colors hover:bg-muted">
            <div className="flex items-center justify-between">
              <Badge variant={article.difficulty === "高级" ? "destructive" : "secondary"}>{article.difficulty}</Badge>
              <span className="text-xs text-muted-foreground">{article.views} 阅读</span>
            </div>
            <div className="mt-4 font-medium">{article.title}</div>
            <p className="mt-2 text-sm text-muted-foreground">{article.description}</p>
            <div className="mt-4 text-xs text-muted-foreground">{article.readTime}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
