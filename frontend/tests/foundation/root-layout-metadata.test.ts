import { describe, expect, it, vi } from "vitest"

vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "--font-geist-sans" }),
  Geist_Mono: () => ({ variable: "--font-geist-mono" })
}))

describe("root layout metadata", () => {
  it("declares the site favicon for the App Router", async () => {
    const { metadata } = await import("../../app/layout")

    expect(metadata.icons).toEqual({
      icon: [
        {
          url: "/favicon.ico?v=20260604",
          sizes: "32x32",
          type: "image/x-icon"
        }
      ],
      shortcut: "/favicon.ico?v=20260604"
    })
  }, 10_000)
})
