import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { learningCategories } from "@/features/learning/content"
import { LearningCategoryPage } from "@/features/learning/learning-category-page"

export function generateStaticParams() {
  return learningCategories.map((category) => ({ category: category.id }))
}

export default async function LearningCategoryRoutePage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params
  return (
    <ProtectedRoute>
      <AppShell>
        <LearningCategoryPage categoryId={decodeURIComponent(category)} />
      </AppShell>
    </ProtectedRoute>
  )
}
