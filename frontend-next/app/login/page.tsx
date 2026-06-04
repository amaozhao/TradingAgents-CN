import { AuthEntryRoute } from "@/components/layout/protected-route"

export default function LoginPage() {
  return (
    <AuthEntryRoute>
      <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
        <section className="w-full max-w-sm rounded-lg border bg-background p-6 shadow-sm">
          <p className="text-sm text-muted-foreground">TradingAgents-CN</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-normal">登录</h1>
          <p className="mt-2 text-sm text-muted-foreground">登录表单将在认证迁移任务中补齐。</p>
        </section>
      </main>
    </AuthEntryRoute>
  )
}
