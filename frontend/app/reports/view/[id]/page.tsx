import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { ReportDetailPage } from "@/features/reports/report-detail-page"

export default async function ReportDetailRoutePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params

  return (
    <ProtectedRoute>
      <AppShell>
        <ReportDetailPage id={id} />
      </AppShell>
    </ProtectedRoute>
  )
}
