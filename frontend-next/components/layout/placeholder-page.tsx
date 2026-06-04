interface PlaceholderPageProps {
  title: string
  description?: string
}

export function PlaceholderPage({ title, description = "页面业务内容将在后续迁移任务中补齐。" }: PlaceholderPageProps) {
  return (
    <section className="rounded-lg border bg-background p-6">
      <p className="text-sm text-muted-foreground">TradingAgents-CN</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-normal">{title}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </section>
  )
}
