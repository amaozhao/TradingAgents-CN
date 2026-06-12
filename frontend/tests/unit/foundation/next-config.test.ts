import { describe, expect, it } from "vitest"

import nextConfig from "../../../next.config"

describe("next config", () => {
  it("preserves API trailing slashes before proxy rewrites", () => {
    expect(nextConfig.skipTrailingSlashRedirect).toBe(true)
  })

  it("keeps trailing-slash API rewrites before the generic API proxy", async () => {
    const rewrites = await nextConfig.rewrites?.()

    expect(rewrites).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: "/api/:path*/" }),
        expect.objectContaining({ source: "/api/:path*" })
      ])
    )
    expect(Array.isArray(rewrites) ? rewrites[0]?.source : undefined).toBe("/api/:path*/")
  })
})
