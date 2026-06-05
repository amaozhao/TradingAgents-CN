import { ReportDetailPage } from "@/features/reports/report-detail-page"

export default async function ReportDetailRoutePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params

  return <ReportDetailPage id={id} />
}
