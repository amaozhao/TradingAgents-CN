"use client"

import { Loader2 } from "lucide-react"

import { Button, type ButtonProps } from "@/components/ui/button"
import { cn } from "@/libs/utils"

interface AsyncButtonProps extends ButtonProps {
  loading?: boolean
  loadingText?: string
}

export function AsyncButton({
  loading = false,
  loadingText,
  disabled,
  children,
  className,
  ...props
}: AsyncButtonProps) {
  return (
    <Button disabled={disabled || loading} className={cn("gap-2", className)} {...props}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : null}
      {loading ? loadingText ?? children : children}
    </Button>
  )
}
