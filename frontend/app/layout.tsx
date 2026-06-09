import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"

import { Providers } from "@/app/providers"
import { AppFrame } from "@/components/layout/app-frame"

import "katex/dist/katex.min.css"
import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"]
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"]
})

export const metadata: Metadata = {
  title: "AGENTrader",
  description: "AGENTrader frontend",
  icons: {
    icon: [
      {
        url: "/favicon.ico?v=20260604",
        sizes: "32x32",
        type: "image/x-icon"
      }
    ],
    shortcut: "/favicon.ico?v=20260604"
  }
}

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-background font-sans antialiased`}>
        <Providers>
          <AppFrame>{children}</AppFrame>
        </Providers>
      </body>
    </html>
  )
}
