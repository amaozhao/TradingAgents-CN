import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
  skipTrailingSlashRedirect: true,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    if (process.env.NODE_ENV === "production") {
      return []
    }

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

    return [
      {
        source: "/api/:path*/",
        destination: `${apiBaseUrl}/api/:path*/`
      },
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`
      }
    ]
  }
}

export default nextConfig
