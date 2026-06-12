"use client"

import type { Table } from "@tanstack/react-table"
import { SlidersHorizontal, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"

interface DataTableToolbarProps<TData> {
  table: Table<TData>
  filterPlaceholder?: string
  globalFilter: string
  onGlobalFilterChange: (value: string) => void
}

export function DataTableToolbar<TData>({
  table,
  filterPlaceholder = "搜索...",
  globalFilter,
  onGlobalFilterChange
}: DataTableToolbarProps<TData>) {
  const canReset = globalFilter.length > 0 || table.getState().columnFilters.length > 0

  return (
    <div className="flex items-center justify-between gap-3 py-3">
      <div className="flex flex-1 items-center gap-2">
        <Input
          placeholder={filterPlaceholder}
          value={globalFilter}
          onChange={(event) => onGlobalFilterChange(event.target.value)}
          className="h-9 max-w-sm"
        />
        {canReset ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onGlobalFilterChange("")
              table.resetColumnFilters()
            }}
          >
            <X className="size-4" />
            重置
          </Button>
        ) : null}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <SlidersHorizontal className="size-4" />
            列
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          {table
            .getAllColumns()
            .filter((column) => column.getCanHide())
            .map((column) => {
              const meta = column.columnDef.meta as { label?: string } | undefined
              const header = column.columnDef.header
              const label = meta?.label || (typeof header === "string" ? header : column.id)

              return (
                <DropdownMenuCheckboxItem
                  key={column.id}
                  checked={column.getIsVisible()}
                  onCheckedChange={(value) => column.toggleVisibility(!!value)}
                >
                  {label}
                </DropdownMenuCheckboxItem>
              )
            })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
