import { zodResolver } from "@hookform/resolvers/zod"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useForm } from "react-hook-form"
import { describe, expect, it, vi } from "vitest"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

const schema = z.object({
  stockCode: z.string().min(1, "请输入股票代码")
})

type FormValues = z.infer<typeof schema>

function StockCodeForm({ onSubmit }: { onSubmit: (values: FormValues) => void }) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      stockCode: ""
    }
  })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="stockCode"
          render={({ field }) => (
            <FormItem>
              <FormLabel>股票代码</FormLabel>
              <FormControl>
                <Input placeholder="请输入" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">提交</Button>
      </form>
    </Form>
  )
}

describe("shadcn form validation", () => {
  it("renders Zod validation errors through FormMessage", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(<StockCodeForm onSubmit={onSubmit} />)
    await user.click(screen.getByRole("button", { name: "提交" }))

    expect(await screen.findByText("请输入股票代码")).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText("请输入")).toHaveAttribute("aria-invalid", "true")
  })
})
