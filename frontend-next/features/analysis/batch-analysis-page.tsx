"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { AsyncButton } from "@/components/feedback/async-button"
import { PageHeader } from "@/components/feedback/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { analysisApi } from "@/libs/api/analysis"

const schema = z.object({
  title: z.string().min(1, "请输入任务标题"),
  symbols: z.string().min(1, "请输入股票代码列表")
})

type Values = z.infer<typeof schema>

export function BatchAnalysisPage() {
  const router = useRouter()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "批量股票分析",
      symbols: ""
    }
  })

  async function onSubmit(values: Values) {
    const symbols = values.symbols
      .split(/[\n,，\s]+/)
      .map((item) => item.trim())
      .filter(Boolean)

    await analysisApi.startBatchAnalysis({
      title: values.title,
      symbols,
      parameters: {
        research_depth: "3"
      }
    })
    toast.success("批量分析任务已创建")
    router.push("/tasks")
  }

  return (
    <div>
      <PageHeader title="批量分析" description="粘贴多个股票代码，一次创建批量分析任务。" />
      <Card>
        <CardHeader>
          <CardTitle>批量参数</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)}>
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>任务标题</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="symbols"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>股票代码列表</FormLabel>
                    <FormControl>
                      <textarea
                        aria-label="股票代码列表"
                        className="min-h-40 w-full rounded-md border bg-background px-3 py-2 text-sm"
                        placeholder="600519&#10;000001&#10;AAPL"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <AsyncButton type="submit" loading={form.formState.isSubmitting} loadingText="创建中...">
                开始批量分析
              </AsyncButton>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
