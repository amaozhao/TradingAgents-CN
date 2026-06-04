import Link from "next/link"

import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { learningArticles, learningCategories } from "@/features/learning/content"

export function LearningHomePage() {
  const recommended = learningArticles.filter((article) => ["what-is-llm", "multi-agent-system", "best-practices"].includes(article.id))

  return (
    <div>
      <PageHeader title="学习中心" description="了解 AI、大模型和智能股票分析。" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {learningCategories.map((category) => {
          const count = learningArticles.filter((article) => article.category === category.id).length
          return (
            <Link key={category.id} href={`/learning/${category.id}`} className="rounded-md border bg-background p-5 transition-colors hover:bg-muted">
              <div className="mb-4 flex size-10 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground">{category.icon}</div>
              <div className="font-medium">{category.title}</div>
              <p className="mt-2 min-h-12 text-sm text-muted-foreground">{category.description}</p>
              <Badge className="mt-4" variant="secondary">{count} 篇文章</Badge>
            </Link>
          )
        })}
      </div>
      <div className="mt-10">
        <h2 className="text-lg font-semibold">推荐阅读</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {recommended.map((article) => (
            <Link key={article.id} href={`/learning/article/${article.id}`} className="rounded-md border bg-background p-5 transition-colors hover:bg-muted">
              <div className="flex items-center justify-between">
                <Badge>{article.categoryTitle}</Badge>
                <span className="text-xs text-muted-foreground">{article.readTime}</span>
              </div>
              <div className="mt-4 font-medium">{article.title}</div>
              <p className="mt-2 text-sm text-muted-foreground">{article.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
