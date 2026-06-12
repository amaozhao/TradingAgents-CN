import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ColumnDef } from "@tanstack/react-table"
import { describe, expect, it } from "vitest"

import { DataTable } from "@/components/data-table/data-table"

interface StockRow {
  code: string
  name: string
}

const columns: ColumnDef<StockRow>[] = [
  {
    accessorKey: "code",
    header: "代码"
  },
  {
    accessorKey: "name",
    header: "名称"
  }
]

describe("DataTable", () => {
  it("shows a loading state", () => {
    render(<DataTable columns={columns} data={[]} loading />)

    expect(screen.getByText("加载中")).toBeInTheDocument()
  })

  it("shows an empty state when no rows are available", () => {
    render(<DataTable columns={columns} data={[]} emptyText="暂无股票" />)

    expect(screen.getByText("暂无股票")).toBeInTheDocument()
  })

  it("renders rows and column headers", () => {
    render(<DataTable columns={columns} data={[{ code: "600519", name: "贵州茅台" }]} />)

    expect(screen.getByRole("columnheader", { name: "代码" })).toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: "名称" })).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "600519" })).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "贵州茅台" })).toBeInTheDocument()
  })

  it("uses translated column headers in the column visibility menu", async () => {
    const user = userEvent.setup()
    render(<DataTable columns={columns} data={[{ code: "600519", name: "贵州茅台" }]} />)

    await user.click(screen.getByRole("button", { name: "列" }))

    expect(screen.getByRole("menuitemcheckbox", { name: "代码" })).toBeInTheDocument()
    expect(screen.getByRole("menuitemcheckbox", { name: "名称" })).toBeInTheDocument()
    expect(screen.queryByRole("menuitemcheckbox", { name: "code" })).not.toBeInTheDocument()
    expect(screen.queryByRole("menuitemcheckbox", { name: "name" })).not.toBeInTheDocument()
  })
})
