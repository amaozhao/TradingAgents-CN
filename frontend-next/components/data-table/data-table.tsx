"use client"

import * as React from "react"
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type Row,
  type RowSelectionState,
  type SortingState,
  type VisibilityState
} from "@tanstack/react-table"

import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table"
import { DataTablePagination } from "@/components/data-table/data-table-pagination"
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  loading?: boolean
  emptyText?: string
  filterPlaceholder?: string
  enableToolbar?: boolean
  enablePagination?: boolean
  enableRowSelection?: boolean
  pageSizeOptions?: number[]
  initialPageSize?: number
  getRowId?: (originalRow: TData, index: number, parent?: Row<TData>) => string
  renderRowActions?: (row: Row<TData>) => React.ReactNode
  onRowClick?: (row: Row<TData>) => void
}

export function DataTable<TData, TValue>({
  columns,
  data,
  loading = false,
  emptyText = "暂无数据",
  filterPlaceholder,
  enableToolbar = true,
  enablePagination = true,
  enableRowSelection = false,
  pageSizeOptions,
  initialPageSize = 10,
  getRowId,
  renderRowActions,
  onRowClick
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({})
  const [globalFilter, setGlobalFilter] = React.useState("")

  const tableColumns = React.useMemo(() => {
    const nextColumns = [...columns]

    if (enableRowSelection) {
      nextColumns.unshift({
        id: "select",
        enableSorting: false,
        enableHiding: false,
        header: ({ table }) => (
          <input
            type="checkbox"
            aria-label="选择全部"
            checked={table.getIsAllPageRowsSelected()}
            onChange={(event) => table.toggleAllPageRowsSelected(event.target.checked)}
            className="size-4 rounded border-input"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label="选择行"
            checked={row.getIsSelected()}
            onChange={(event) => row.toggleSelected(event.target.checked)}
            onClick={(event) => event.stopPropagation()}
            className="size-4 rounded border-input"
          />
        )
      } as ColumnDef<TData, TValue>)
    }

    if (renderRowActions) {
      nextColumns.push({
        id: "actions",
        enableHiding: false,
        header: "操作",
        cell: ({ row }) => renderRowActions(row)
      } as ColumnDef<TData, TValue>)
    }

    return nextColumns
  }, [columns, enableRowSelection, renderRowActions])

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table intentionally returns table instance methods.
  const table = useReactTable({
    data,
    columns: tableColumns,
    getRowId,
    enableRowSelection,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter
    },
    initialState: {
      pagination: {
        pageSize: initialPageSize
      }
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel()
  })

  const visibleColumnCount = Math.max(table.getVisibleLeafColumns().length, 1)

  return (
    <div className="w-full">
      {enableToolbar ? (
        <DataTableToolbar
          table={table}
          filterPlaceholder={filterPlaceholder}
          globalFilter={globalFilter}
          onGlobalFilterChange={setGlobalFilter}
        />
      ) : null}
      <div className="rounded-md border bg-background">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={visibleColumnCount} className="h-24 text-center">
                  <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground">
                    <Skeleton className="h-3 w-48" />
                    <span>加载中</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  onClick={() => onRowClick?.(row)}
                  className={onRowClick ? "cursor-pointer" : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={visibleColumnCount} className="h-24 text-center text-muted-foreground">
                  {emptyText}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {enablePagination ? <DataTablePagination table={table} pageSizeOptions={pageSizeOptions} /> : null}
    </div>
  )
}

export type { ColumnDef, Row }
