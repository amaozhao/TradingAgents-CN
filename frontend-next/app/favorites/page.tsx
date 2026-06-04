import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { FavoritesPage } from "@/features/favorites/favorites-page"

export default function FavoritesRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <FavoritesPage />
      </AppShell>
    </ProtectedRoute>
  )
}
