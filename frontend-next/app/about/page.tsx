import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { AboutPage } from "@/features/about/about-page"

export default function AboutRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <AboutPage />
      </AppShell>
    </ProtectedRoute>
  )
}
