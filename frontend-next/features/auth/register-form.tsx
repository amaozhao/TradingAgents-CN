"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { AsyncButton } from "@/components/feedback/async-button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { authApi } from "@/libs/api/auth"

const registerSchema = z
  .object({
    username: z.string().min(1, "请输入用户名"),
    email: z.string().email("请输入有效邮箱"),
    password: z.string().min(6, "密码长度不能少于6位"),
    confirm_password: z.string().min(6, "请确认密码"),
    agreement: z.boolean().refine(Boolean, "请先同意使用条款")
  })
  .refine((values) => values.password === values.confirm_password, {
    path: ["confirm_password"],
    message: "两次输入的密码不一致"
  })

type RegisterValues = z.infer<typeof registerSchema>

export function RegisterForm() {
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      email: "",
      password: "",
      confirm_password: "",
      agreement: false
    }
  })

  async function onSubmit(values: RegisterValues) {
    await authApi.register(values)
    toast.success("注册成功，请登录")
    form.reset()
  }

  return (
    <Form {...form}>
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="username"
          render={({ field }) => (
            <FormItem>
              <FormLabel>用户名</FormLabel>
              <FormControl>
                <Input placeholder="请输入用户名" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>邮箱</FormLabel>
              <FormControl>
                <Input type="email" placeholder="请输入邮箱" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>密码</FormLabel>
                <FormControl>
                  <Input type="password" placeholder="请输入密码" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>确认密码</FormLabel>
                <FormControl>
                  <Input type="password" placeholder="请再次输入" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="agreement"
          render={({ field }) => (
            <FormItem>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={field.value}
                  onChange={(event) => field.onChange(event.target.checked)}
                  className="size-4 rounded border-input"
                />
                我已阅读并同意学习平台使用条款
              </label>
              <FormMessage />
            </FormItem>
          )}
        />
        <AsyncButton type="submit" className="w-full" loading={form.formState.isSubmitting} loadingText="注册中...">
          注册
        </AsyncButton>
      </form>
    </Form>
  )
}
