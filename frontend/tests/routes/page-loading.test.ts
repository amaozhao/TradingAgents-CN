import { existsSync, readdirSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { describe, expect, it } from "vitest"

function collectPageFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      return collectPageFiles(path)
    }
    return entry.isFile() && entry.name === "page.tsx" ? [path] : []
  })
}

const routePageFiles = collectPageFiles(join(process.cwd(), "app"))

describe("page route loading states", () => {
  it("defines a shared loading fallback for every navigable page route", () => {
    expect(routePageFiles.length).toBeGreaterThan(0)

    for (const pageFile of routePageFiles) {
      expect(existsSync(pageFile), `${pageFile} should exist`).toBe(true)

      const loadingFile = join(dirname(pageFile), "loading.tsx")
      expect(existsSync(loadingFile), `${loadingFile} should exist`).toBe(true)
      expect(readFileSync(loadingFile, "utf8")).toContain("PageLoading")
    }
  })

  it("keeps the scheduler page from showing empty data while queries are loading", () => {
    const schedulerSource = readFileSync(
      join(process.cwd(), "features", "settings", "settings-pages.tsx"),
      "utf8"
    )

    expect(schedulerSource).toContain("schedulerInitialLoading")
    expect(schedulerSource).toContain("executionsQuery.isLoading")
  })
})

describe("app shell routing ownership", () => {
  it("keeps the persistent app shell out of individual route pages", () => {
    for (const pageFile of routePageFiles) {
      if (pageFile.endsWith(join("app", "login", "page.tsx"))) continue

      const source = readFileSync(pageFile, "utf8")
      expect(source, `${pageFile} should not own AppShell`).not.toContain("AppShell")
      expect(source, `${pageFile} should not own ProtectedRoute`).not.toContain("ProtectedRoute")
    }
  })
})
