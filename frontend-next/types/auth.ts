export interface User {
  id?: string | number
  username?: string
  email?: string
  avatar?: string
  total_analyses?: number
  successful_analyses?: number
  failed_analyses?: number
  daily_quota?: number
  concurrent_limit?: number
  preferences?: Record<string, unknown>
  [key: string]: unknown
}

export interface LoginForm {
  username: string
  password: string
}

export interface RegisterForm {
  username: string
  email: string
  password: string
}
