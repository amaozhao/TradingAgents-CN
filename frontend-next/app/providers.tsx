"use client"

import { ThemeProvider } from "next-themes"
import type { ThemeProviderProps } from "next-themes"

type ProvidersProps = ThemeProviderProps & {
  children: React.ReactNode
}

export function Providers({ children, ...props }: ProvidersProps) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </ThemeProvider>
  )
}
