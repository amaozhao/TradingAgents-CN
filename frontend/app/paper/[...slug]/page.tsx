import { notFound, redirect } from "next/navigation"

interface PaperMarkdownRedirectPageProps {
  params: Promise<{
    slug: string[]
  }>
}

export default async function PaperMarkdownRedirectPage({ params }: PaperMarkdownRedirectPageProps) {
  const { slug } = await params
  const fileName = slug.join("/")

  if (!fileName.endsWith(".md")) {
    notFound()
  }

  redirect(`/learning/article/${fileName.slice(0, -3)}`)
}
