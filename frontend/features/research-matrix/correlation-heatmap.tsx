const symbols = ["600519", "000001", "300750"]
const values = [
  [1, 0.62, -0.18],
  [0.62, 1, 0.34],
  [-0.18, 0.34, 1]
]

export function CorrelationHeatmap() {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">Heatmap</h2>
      <div className="grid grid-cols-[80px_repeat(3,minmax(54px,1fr))] gap-1 text-center text-xs">
        <span />
        {symbols.map((symbol) => <span key={symbol} className="font-medium">{symbol}</span>)}
        {symbols.map((row, rowIndex) => (
          <div key={row} className="contents">
            <span className="py-2 text-left font-medium">{row}</span>
            {values[rowIndex].map((value, index) => (
              <span key={`${row}-${symbols[index]}`} className={cellClass(value)}>
                {value.toFixed(2)}
              </span>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}

function cellClass(value: number) {
  const base = "rounded px-2 py-2 font-medium"
  if (value > 0.7) return `${base} bg-red-100 text-red-700`
  if (value > 0.3) return `${base} bg-amber-100 text-amber-700`
  if (value < 0) return `${base} bg-emerald-100 text-emerald-700`
  return `${base} bg-muted`
}
