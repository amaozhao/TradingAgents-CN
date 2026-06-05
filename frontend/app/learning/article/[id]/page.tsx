import { learningArticles } from "@/features/learning/content"
import { LearningArticlePage } from "@/features/learning/learning-article-page"

export function generateStaticParams() {
  return learningArticles.map((article) => ({ id: article.id }))
}

export default async function LearningArticleRoutePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <LearningArticlePage articleId={decodeURIComponent(id)} />
}
