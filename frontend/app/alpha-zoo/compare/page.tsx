import { Suspense } from "react"

import { AlphaComparePage } from "@/features/alpha-zoo/alpha-compare-page"

export default function Page() {
  return (
    <Suspense>
      <AlphaComparePage />
    </Suspense>
  )
}
