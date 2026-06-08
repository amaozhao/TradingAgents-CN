import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const factors = [
  { id: "alpha101_001", family: "alpha101", columns: ["close", "volume"], state: "alive" },
  { id: "gtja191_001", family: "gtja191", columns: ["open", "high", "low"], state: "reversed" },
  { id: "qlib158_001", family: "qlib158", columns: ["vwap", "amount"], state: "dead" }
]

export function AlphaFactorTable() {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">因子表</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>因子</TableHead>
            <TableHead>Zoo</TableHead>
            <TableHead>字段</TableHead>
            <TableHead>分类</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {factors.map((factor) => (
            <TableRow key={factor.id}>
              <TableCell className="font-medium">{factor.id}</TableCell>
              <TableCell>{factor.family}</TableCell>
              <TableCell>{factor.columns.join(", ")}</TableCell>
              <TableCell><Badge variant="secondary">{factor.state}</Badge></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}
