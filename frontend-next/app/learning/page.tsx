import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { LearningHomePage } from "@/features/learning/learning-home-page"

export default function LearningRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <LearningHomePage />
      </AppShell>
    </ProtectedRoute>
  )
}
