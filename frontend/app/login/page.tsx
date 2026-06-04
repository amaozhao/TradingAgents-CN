import Image from "next/image"

import { AuthEntryRoute } from "@/components/layout/protected-route"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LoginForm } from "@/features/auth/login-form"
import { RegisterForm } from "@/features/auth/register-form"

export default function LoginPage() {
  return (
    <AuthEntryRoute>
      <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
        <section className="w-full max-w-md">
          <div className="mb-8 text-center">
            <Image src="/logo.svg" alt="TradingAgents-CN" width={64} height={64} className="mx-auto mb-4" />
            <h1 className="text-3xl font-semibold tracking-normal">TradingAgents-CN</h1>
            <p className="mt-2 text-sm text-muted-foreground">多智能体股票分析学习平台</p>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>登录</CardTitle>
              <CardDescription>开源版默认账号：admin / admin123</CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="login">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="login">登录</TabsTrigger>
                  <TabsTrigger value="register">注册</TabsTrigger>
                </TabsList>
                <TabsContent value="login" className="mt-4">
                  <LoginForm />
                </TabsContent>
                <TabsContent value="register" className="mt-4">
                  <RegisterForm />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
          <p className="mt-6 text-center text-xs leading-6 text-muted-foreground">
            平台中的分析结论由 AI 自动生成，仅用于学习、研究与交流，不构成投资建议。
          </p>
        </section>
      </main>
    </AuthEntryRoute>
  )
}
