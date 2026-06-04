import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { SchedulerManagementPage } from "@/features/settings/settings-pages"

export default function SettingsSchedulerRoutePage() {
  return <ProtectedRoute><AppShell><SchedulerManagementPage /></AppShell></ProtectedRoute>
}
