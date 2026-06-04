import { redirect } from "next/navigation"

interface PaperMarkdownRedirectPageProps {
  params: Promise<{
    name: string
  }>
}

export default async function PaperMarkdownRedirectPage({ params }: PaperMarkdownRedirectPageProps) {
  const { name } = await params
  redirect(`/learning/article/${name}`)
}
