export function formatDateTime(timestamp: string | number | Date): string {
  const date = new Date(timestamp)

  if (Number.isNaN(date.getTime())) {
    return String(timestamp)
  }

  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  })
}
