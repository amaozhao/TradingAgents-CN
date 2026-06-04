"use client"

import { useState, useSyncExternalStore } from "react"
import { CheckCircle2, Cpu, Database, Settings } from "lucide-react"

import { AsyncButton } from "@/components/feedback/async-button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

const WIZARD_DONE_KEY = "config-wizard-completed"

const steps = [
  { title: "欢迎", icon: Settings },
  { title: "数据库配置", icon: Database },
  { title: "大模型配置", icon: Cpu },
  { title: "完成", icon: CheckCircle2 }
]

export function ConfigWizard() {
  const shouldShow = useSyncExternalStore(
    () => () => undefined,
    () => localStorage.getItem(WIZARD_DONE_KEY) !== "true",
    () => false
  )
  const [dismissed, setDismissed] = useState(false)
  const [step, setStep] = useState(0)
  const open = shouldShow && !dismissed

  function finish() {
    localStorage.setItem(WIZARD_DONE_KEY, "true")
    setDismissed(true)
  }

  const StepIcon = steps[step]?.icon ?? Settings

  return (
    <Dialog
      open={open}
      onOpenChange={
        step > 0
          ? (nextOpen) => {
              if (!nextOpen) setDismissed(true)
            }
          : undefined
      }
    >
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>配置向导</DialogTitle>
          <DialogDescription>通过几个关键步骤确认系统已经具备股票分析运行条件。</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-4 gap-2">
          {steps.map((item, index) => {
            const Icon = item.icon
            return (
              <div
                key={item.title}
                className={index === step ? "rounded-md border bg-muted p-3" : "rounded-md border p-3 text-muted-foreground"}
              >
                <Icon className="mb-2 size-4" />
                <div className="text-xs font-medium">{item.title}</div>
              </div>
            )
          })}
        </div>
        <div className="min-h-52 rounded-md border p-5">
          <StepIcon className="mb-4 size-8 text-primary" />
          {step === 0 ? (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">欢迎使用 TradingAgents-CN</h3>
              <p className="text-sm text-muted-foreground">
                如果您已经配置过系统，可以跳过此向导；也可以稍后在配置管理页面修改这些设置。
              </p>
            </div>
          ) : step === 1 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Input defaultValue="localhost" aria-label="PostgreSQL 主机" />
              <Input defaultValue="5432" aria-label="PostgreSQL 端口" />
              <Input defaultValue="trading_agents" aria-label="数据库名" />
              <Input defaultValue="6379" aria-label="Redis 端口" />
            </div>
          ) : step === 2 ? (
            <div className="grid gap-4">
              <Input defaultValue="dashscope" aria-label="大模型提供商" />
              <Input type="password" placeholder="API 密钥" aria-label="API 密钥" />
              <Input defaultValue="qwen-turbo" aria-label="模型名称" />
            </div>
          ) : (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">准备完成</h3>
              <p className="text-sm text-muted-foreground">可以开始进行单股分析、股票筛选和学习中心内容浏览。</p>
            </div>
          )}
        </div>
        <DialogFooter>
          {step > 0 ? (
            <AsyncButton variant="outline" onClick={() => setStep((value) => value - 1)}>
              上一步
            </AsyncButton>
          ) : null}
          {step < steps.length - 1 ? (
            <AsyncButton onClick={() => setStep((value) => value + 1)}>下一步</AsyncButton>
          ) : (
            <AsyncButton onClick={finish}>完成</AsyncButton>
          )}
          <AsyncButton variant="ghost" onClick={finish}>
            跳过
          </AsyncButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
