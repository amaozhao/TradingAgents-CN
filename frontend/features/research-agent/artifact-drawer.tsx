import { Button } from "@/components/ui/button"

const artifacts = [
  { id: "artifact-alpha-a", type: "Alpha Bench" },
  { id: "artifact-matrix-a", type: "Correlation Matrix" },
  { id: "report-draft-a", type: "Final Report" }
]

export function ArtifactDrawer() {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">产物抽屉</h2>
      <div className="space-y-2">
        {artifacts.map((artifact) => (
          <div key={artifact.id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
            <span>{artifact.type}</span>
            <Button size="sm" variant="outline">打开</Button>
          </div>
        ))}
      </div>
    </section>
  )
}
