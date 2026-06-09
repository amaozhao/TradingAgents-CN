import { AlphaFactorDetailPage } from "@/features/alpha-zoo/alpha-factor-detail-page"

interface PageProps {
  params: Promise<{ id: string }>
}

export default async function Page({ params }: PageProps) {
  const { id } = await params

  return <AlphaFactorDetailPage alphaId={decodeURIComponent(id)} />
}
