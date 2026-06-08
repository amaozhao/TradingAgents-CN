import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { AlphaFactor } from "@/libs/api/alpha-zoo"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

const TABLE_COPY = {
  "zh-CN": {
    title: "Alpha 因子目录",
    loadingBadge: "加载中",
    countSuffix: "个因子",
    loading: "正在加载真实 Alpha 因子库...",
    empty: "没有匹配的因子",
    select: "选择",
    factor: "ID",
    zoo: "因子库",
    theme: "主题",
    universe: "市场",
    decay: "衰减天数"
  },
  "en-US": {
    title: "Alpha catalogue",
    loadingBadge: "Loading",
    countSuffix: "factors",
    loading: "Loading the real Alpha Zoo...",
    empty: "No matching factors",
    select: "Select",
    factor: "ID",
    zoo: "Zoo",
    theme: "Theme",
    universe: "Universe",
    decay: "Decay (days)"
  }
} satisfies Record<AppLanguage, Record<string, string>>

interface AlphaFactorTableProps {
  factors: AlphaFactor[]
  loading?: boolean
  selectedIds?: Set<string>
  onToggleSelected?: (factorId: string) => void
}

export function AlphaFactorTable({ factors, loading = false, selectedIds, onToggleSelected }: AlphaFactorTableProps) {
  const language = useAppStore((state) => state.language)
  const copy = TABLE_COPY[language]

  return (
    <section className="overflow-hidden rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-3 border-b bg-muted/30 px-4 py-3">
        <h2 className="text-base font-semibold">{copy.title}</h2>
        <Badge variant="secondary">{loading ? copy.loadingBadge : `${factors.length} ${copy.countSuffix}`}</Badge>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/20">
              <TableHead className="w-12"><span className="sr-only">{copy.select}</span></TableHead>
              <TableHead className="min-w-[300px]">{copy.factor}</TableHead>
              <TableHead>{copy.zoo}</TableHead>
              <TableHead className="min-w-[180px]">{copy.theme}</TableHead>
              <TableHead className="min-w-[220px]">{copy.universe}</TableHead>
              <TableHead className="text-right">{copy.decay}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">{copy.loading}</TableCell>
              </TableRow>
            ) : factors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">{copy.empty}</TableCell>
              </TableRow>
            ) : (
              factors.map((factor) => (
                <TableRow key={factor.id} className="hover:bg-muted/30">
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selectedIds?.has(factor.id) || false}
                      onChange={() => onToggleSelected?.(factor.id)}
                      aria-label={`${copy.select} ${factor.id}`}
                      className="size-4 rounded border-input accent-primary"
                    />
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    <span className="text-primary">{factor.id}</span>
                    {factor.nickname ? <span className="ml-2 font-sans text-muted-foreground">{factor.nickname}</span> : null}
                  </TableCell>
                  <TableCell className="text-xs">{factor.zoo}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{factor.theme.join(", ") || "-"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{factor.universe.join(", ") || "-"}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{factor.decay_horizon ?? "-"}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}
