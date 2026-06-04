import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { TaskCenterPage } from "@/features/tasks/task-center-page"

export default function TasksPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <TaskCenterPage />
      </AppShell>
    </ProtectedRoute>
  )
}
