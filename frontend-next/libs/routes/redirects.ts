import { redirectRoutes } from "@/libs/routes/route-config"

export function getRedirectDestination(source: string, params?: Record<string, string>) {
  const redirect = redirectRoutes.find((route) => route.source === source)
  if (!redirect) return null

  let destination = redirect.destination

  for (const [key, value] of Object.entries(params || {})) {
    destination = destination.replace(`[${key}]`, value)
  }

  return destination
}
