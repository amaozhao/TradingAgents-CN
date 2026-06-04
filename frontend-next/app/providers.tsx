"use client"

import { ThemeProvider } from "next-themes"
import type { ThemeProviderProps } from "next-themes"
import { QueryClientProvider } from "@tanstack/react-query"

import { GlobalToaster } from "@/components/feedback/global-toaster"
import { queryClient } from "@/libs/api/query-client"

type ProvidersProps = ThemeProviderProps & {
  children: React.ReactNode
}

export function Providers({ children, ...props }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
        {...props}
      >
        {children}
        <GlobalToaster />
      </ThemeProvider>
    </QueryClientProvider>
  )
}
