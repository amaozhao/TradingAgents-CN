import { StockDetailPage } from "@/features/stocks/stock-detail-page"

export default async function StockDetailRoutePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params
  return <StockDetailPage code={decodeURIComponent(code)} />
}
