import { redirect } from "next/navigation"

export default function AnalysisHistoryRedirectPage() {
  redirect("/tasks?tab=completed")
}
