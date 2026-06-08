import { Play } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function AlphaBenchRunner() {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">Bench Runner</h2>
      <div className="grid gap-3">
        <div className="grid gap-2">
          <Label>候选股票</Label>
          <Input defaultValue="600519,000001,300750" />
        </div>
        <div className="grid gap-2">
          <Label>评估模式</Label>
          <Select defaultValue="bench">
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="bench">Bench</SelectItem>
              <SelectItem value="compare">Compare</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button><Play className="mr-2 size-4" />运行</Button>
      </div>
    </section>
  )
}
