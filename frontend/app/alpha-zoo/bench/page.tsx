import { Suspense } from "react"

import { AlphaBenchPage } from "@/features/alpha-zoo/alpha-bench-page"

export default function Page() {
  return (
    <Suspense>
      <AlphaBenchPage />
    </Suspense>
  )
}
