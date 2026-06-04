"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { AsyncButton } from "@/components/feedback/async-button"
import { PageHeader } from "@/components/feedback/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DatePicker } from "@/components/ui/date-picker"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { analysisApi } from "@/libs/api/analysis"

const schema = z.object({
  market_type: z.enum(["A股", "港股", "美股"]),
  stock_symbol: z.string().min(1, "请输入股票代码"),
  analysis_date: z.string().min(1, "请选择分析日期"),
  research_depth: z.string(),
  analysts: z.array(z.string()).min(1, "请选择至少一个分析师")
})

type Values = z.infer<typeof schema>

const analystOptions = ["市场分析师", "基本面分析师", "新闻分析师", "社媒分析师"]

export function SingleAnalysisPage() {
  const router = useRouter()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      market_type: "A股",
      stock_symbol: "",
      analysis_date: new Date().toISOString().slice(0, 10),
      research_depth: "3",
      analysts: ["市场分析师", "基本面分析师", "新闻分析师"]
    }
  })

  async function onSubmit(values: Values) {
    await analysisApi.startSingleAnalysis({
      symbol: values.stock_symbol,
      parameters: {
        market_type: values.market_type,
        analysis_date: values.analysis_date,
        research_depth: values.research_depth,
        selected_analysts: values.analysts
      }
    })
    toast.success("分析任务已创建")
    router.push("/tasks")
  }

  return (
    <div>
      <PageHeader title="单股分析" description="选择市场、股票代码、分析日期和智能体角色，创建单股分析任务。" />
      <Card>
        <CardHeader>
          <CardTitle>分析参数</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form className="grid gap-5 lg:grid-cols-2" onSubmit={form.handleSubmit(onSubmit)}>
              <FormField
                control={form.control}
                name="market_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>市场</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="A股">A股</SelectItem>
                        <SelectItem value="港股">港股</SelectItem>
                        <SelectItem value="美股">美股</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="stock_symbol"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>股票代码</FormLabel>
                    <FormControl>
                      <Input placeholder="例如 600519" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="analysis_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>分析日期</FormLabel>
                    <FormControl>
                      <DatePicker value={field.value} onChange={field.onChange} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="research_depth"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>研究深度</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {[1, 2, 3, 4, 5].map((depth) => (
                          <SelectItem key={depth} value={`${depth}`}>{depth} 级</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="analysts"
                render={({ field }) => (
                  <FormItem className="lg:col-span-2">
                    <FormLabel>分析师</FormLabel>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {analystOptions.map((analyst) => (
                        <label key={analyst} className="flex items-center gap-2 rounded-md border p-3 text-sm">
                          <input
                            type="checkbox"
                            checked={field.value.includes(analyst)}
                            onChange={(event) => {
                              field.onChange(
                                event.target.checked
                                  ? [...field.value, analyst]
                                  : field.value.filter((item) => item !== analyst)
                              )
                            }}
                          />
                          {analyst}
                        </label>
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="lg:col-span-2">
                <AsyncButton type="submit" loading={form.formState.isSubmitting} loadingText="创建中...">
                  开始分析
                </AsyncButton>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
