import { ConfigWizard } from "@/features/config/config-wizard"
import { DashboardPage as DashboardFeature } from "@/features/dashboard/dashboard-page"

export default function DashboardPage() {
  return (
    <>
      <DashboardFeature />
      <ConfigWizard />
    </>
  )
}
