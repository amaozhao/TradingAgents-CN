"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useRouter } from "next/navigation"
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
import { useAuthStore } from "@/stores/auth-store"

const loginSchema = z.object({
  username: z.string().min(1, "请输入用户名"),
  password: z.string().min(6, "密码长度不能少于6位"),
  remember_me: z.boolean().optional()
})

type LoginValues = z.infer<typeof loginSchema>
const showDefaultCredentials = process.env.NODE_ENV !== "production"

export function LoginForm() {
  const router = useRouter()
  const setAuthInfo = useAuthStore((state) => state.setAuthInfo)
  const getAndClearRedirectPath = useAuthStore((state) => state.getAndClearRedirectPath)
  const loginLoading = useAuthStore((state) => state.loginLoading)
  const setLoginLoading = useAuthStore((state) => state.setLoginLoading)

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
      remember_me: false
    }
  })

  async function onSubmit(values: LoginValues) {
    if (loginLoading) return

    setLoginLoading(true)
    try {
      const response = await authApi.login(values)
      const data = response.data
      setAuthInfo(data.access_token, data.refresh_token, data.user)
      toast.success("登录成功")
      router.replace(getAndClearRedirectPath())
    } catch {
      toast.error("用户名或密码错误")
    } finally {
      setLoginLoading(false)
    }
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
                <Input autoComplete="username" placeholder="请输入用户名" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>密码</FormLabel>
              <FormControl>
                <Input autoComplete="current-password" type="password" placeholder="请输入密码" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="remember_me"
          render={({ field }) => (
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={field.value}
                onChange={(event) => field.onChange(event.target.checked)}
                className="size-4 rounded border-input"
              />
              记住我
            </label>
          )}
        />
        <AsyncButton type="submit" className="w-full" loading={loginLoading} loadingText="登录中...">
          登录
        </AsyncButton>
        {showDefaultCredentials ? (
          <p className="text-center text-xs text-muted-foreground">
            开发默认账号：admin / admin123
          </p>
        ) : null}
      </form>
    </Form>
  )
}
