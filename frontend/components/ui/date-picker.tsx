"use client"

import * as React from "react"
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/libs/utils"

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]

export interface DatePickerProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange" | "value"> {
  value?: string
  onChange?: (value: string) => void
  placeholder?: string
}

const DatePicker = React.forwardRef<HTMLButtonElement, DatePickerProps>(
  ({ value, onChange, placeholder = "选择日期", className, disabled, ...props }, ref) => {
    const selectedDate = React.useMemo(() => parseDateKey(value), [value])
    const selectedTime = selectedDate?.getTime()
    const initialMonth = selectedDate ?? new Date()
    const [open, setOpen] = React.useState(false)
    const [viewYear, setViewYear] = React.useState(initialMonth.getFullYear())
    const [viewMonth, setViewMonth] = React.useState(initialMonth.getMonth())

    React.useEffect(() => {
      if (!selectedDate) return
      setViewYear(selectedDate.getFullYear())
      setViewMonth(selectedDate.getMonth())
    }, [selectedDate, selectedTime])

    const dates = React.useMemo(() => buildCalendarDates(viewYear, viewMonth), [viewYear, viewMonth])
    const todayKey = formatDateKey(new Date())
    const selectedKey = selectedDate ? formatDateKey(selectedDate) : undefined

    const changeMonth = (offset: number) => {
      const next = new Date(viewYear, viewMonth + offset, 1)
      setViewYear(next.getFullYear())
      setViewMonth(next.getMonth())
    }

    const selectDate = (date: Date) => {
      onChange?.(formatDateKey(date))
      setOpen(false)
    }

    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            ref={ref}
            type="button"
            disabled={disabled}
            className={cn(
              "flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-1 text-left text-base shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
              !value && "text-muted-foreground",
              className
            )}
            {...props}
          >
            <span>{value ? formatDisplayDate(value) : placeholder}</span>
            <Calendar className="size-4 text-muted-foreground" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[20rem] p-0">
          <div className="border-b px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label="上个月"
                onClick={() => changeMonth(-1)}
              >
                <ChevronLeft />
              </Button>
              <div className="min-w-0 text-center">
                <div className="text-sm font-semibold">{viewYear}年{String(viewMonth + 1).padStart(2, "0")}月</div>
                <div className="text-xs text-muted-foreground">选择分析日期</div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label="下个月"
                onClick={() => changeMonth(1)}
              >
                <ChevronRight />
              </Button>
            </div>
          </div>

          <div className="p-4">
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-muted-foreground">
              {WEEKDAYS.map((weekday) => (
                <div key={weekday} className="flex h-7 items-center justify-center">
                  {weekday}
                </div>
              ))}
            </div>
            <div className="mt-1 grid grid-cols-7 gap-1">
              {dates.map((date) => {
                const dateKey = formatDateKey(date)
                const inViewMonth = date.getMonth() === viewMonth
                const selected = dateKey === selectedKey
                const today = dateKey === todayKey

                return (
                  <button
                    key={dateKey}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => selectDate(date)}
                    className={cn(
                      "flex h-8 items-center justify-center rounded-md text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                      !inViewMonth && "text-muted-foreground/55",
                      today && "border border-primary/40",
                      selected && "bg-primary font-semibold text-primary-foreground hover:bg-primary hover:text-primary-foreground"
                    )}
                  >
                    {date.getDate()}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="flex items-center justify-between border-t px-4 py-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                onChange?.("")
                setOpen(false)
              }}
            >
              清除
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => selectDate(new Date())}>
              今天
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    )
  }
)
DatePicker.displayName = "DatePicker"

function buildCalendarDates(year: number, month: number) {
  const firstDay = new Date(year, month, 1)
  const mondayOffset = (firstDay.getDay() + 6) % 7
  const start = new Date(year, month, 1 - mondayOffset)

  return Array.from({ length: 42 }, (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index))
}

function parseDateKey(value?: string) {
  if (!value) return undefined
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return undefined

  const year = Number(match[1])
  const month = Number(match[2]) - 1
  const day = Number(match[3])
  const date = new Date(year, month, day)

  if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) {
    return undefined
  }

  return date
}

function formatDateKey(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function formatDisplayDate(value: string) {
  return value.replaceAll("-", "/")
}

export { DatePicker }
