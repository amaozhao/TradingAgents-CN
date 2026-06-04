import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { StockDetailPage } from "@/features/stocks/stock-detail-page"

export default async function StockDetailRoutePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params
  return (
    <ProtectedRoute>
      <AppShell>
        <StockDetailPage code={decodeURIComponent(code)} />
      </AppShell>
    </ProtectedRoute>
  )
}
