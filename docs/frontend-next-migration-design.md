# Frontend Next Migration Design

## 目标

将原 `frontend/` 的 Vue 3 + Vite 前端迁移为 Next.js App Router + React 前端。迁移目标是功能等价，不借迁移机会重做产品流程、后端接口、URL 结构或权限模型。

切流完成后，Next 版本位于正式 `frontend/` 目录，旧 Vue 版本保留在 `frontend-vue/` 作为回滚基线。

## 已确认决策

| 项 | 决策 |
| --- | --- |
| 迁移目标 | 功能等价迁移 |
| 切换策略 | 并行目录迁移，最后整体切流 |
| 首版范围 | 全量等价后再切流 |
| UI 等价 | 功能和布局等价，允许新视觉 |
| UI 栈 | shadcn/ui + Radix + Tailwind |
| 样式 | Tailwind + shadcn CSS variables + 少量 CSS Modules |
| 渲染 | 首版以 Client Components 为主 |
| 部署 | Next standalone Node runtime |
| API 代理 | 生产继续外层 Nginx 代理 `/api`，开发使用 Next rewrites |
| 认证 | 首版保持 localStorage token |
| 状态 | Zustand + TanStack Query |
| API 层 | 保留 axios 语义，页面层接 TanStack Query |
| WebSocket | 保持现有 `/api/ws/notifications?token=` 协议 |
| 路由 | 完全保持当前 URL 和重定向规则 |
| 路由保护 | 客户端保护 |
| 图表 | 保留 ECharts，React 侧使用薄封装或 `echarts-for-react` |
| Markdown/Mermaid | 保持现有内容、渲染能力和路径兼容 |
| 包管理器 | `frontend/` 使用 pnpm |
| 目录策略 | `frontend/` 为 Next 正式前端，`frontend-vue/` 为旧 Vue 回滚基线 |
| 验证 | 完整验收门槛 |
| 表格 | TanStack Table + shadcn Table 自封装 `DataTable` |
| 表单 | React Hook Form + Zod + shadcn Form |
| Toast/Dialog | sonner + shadcn/Radix Dialog + AlertDialog |
| 图标 | lucide-react |
| 主题 | shadcn CSS variables + next-themes |
| i18n | 中文界面，不引入完整 i18n 框架 |
| 测试 | Vitest + React Testing Library + Playwright |
| 代码结构 | 使用 `libs/`，不使用 `lib/` |
| shadcn 落地 | CLI 生成组件源码到 `components/ui` |
| shadcn 配置 | `new-york`、`slate`、CSS variables、lucide、RSC yes |
| 老 Vue | 保留在 `frontend-vue/`，只做必要 bugfix，不做新功能 |
| 提交方式 | 多阶段提交或 PR |

## 非目标

- 不改后端认证协议。
- 不把 localStorage token 改为 httpOnly cookie。
- 不引入 Next middleware 做服务端认证。
- 不改现有 REST API 和 WebSocket 协议。
- 不重命名现有 URL。
- 不把当前 Vue 前端和 Next 前端做生产分路径灰度。
- 不引入完整国际化框架。
- 不在首版系统性使用 Server Components、Server Actions 或 SSR 数据获取。

## 当前迁移输入

迁移输入来自旧 Vue 前端，现保留在 `frontend-vue/`。其技术形态为 Vite + Vue 3 + Pinia + Vue Router + Element Plus。主要耦合点包括：

- 路由、菜单、页面标题、认证守卫集中在 `frontend-vue/src/router/index.ts`。
- API 请求层在 `frontend-vue/src/api/request.ts`，依赖 axios、Pinia、Vue Router 和 Element Plus message。
- 认证状态在 `frontend-vue/src/stores/auth.ts`，使用 localStorage 中的 `auth-token`、`refresh-token`、`user-info`。
- 通知 WebSocket 在 `frontend-vue/src/stores/notifications.ts`，连接当前 host 下的 `/api/ws/notifications?token=...`。
- 旧 Docker 前端构建为静态文件，由 Nginx 服务；Next 切流后改为 standalone Node runtime。

## 目标架构

`frontend/` 使用 Next App Router。`app/` 只负责路由入口和轻量 page 组装，业务逻辑下沉到 `features/`，通用基础能力放到 `libs/`、`stores/`、`hooks/` 和 `components/`。

```text
frontend/
  app/
    layout.tsx
    providers.tsx
    login/page.tsx
    dashboard/page.tsx
    analysis/single/page.tsx
    analysis/batch/page.tsx
  components/
    ui/
    layout/
    data-table/
    feedback/
    charts/
  features/
    analysis/
    reports/
    settings/
    stocks/
    learning/
    notifications/
  libs/
    api/
    routes/
    auth/
    utils/
  stores/
  hooks/
  types/
  styles/
  tests/
```

### Routing

Next 文件路由必须保持现有 URL：

- `/dashboard`
- `/analysis/single`
- `/analysis/batch`
- `/screening`
- `/favorites`
- `/learning`
- `/learning/:category`
- `/learning/article/:id`
- `/stocks/:code`
- `/tasks`
- `/queue` redirects to `/tasks`
- `/analysis/history` redirects to `/tasks?tab=completed`
- `/reports`
- `/reports/view/:id`
- `/reports/token`
- `/settings`
- `/settings/config`
- `/settings/database`
- `/settings/logs`
- `/settings/system-logs`
- `/settings/sync`
- `/settings/cache`
- `/settings/usage`
- `/settings/scheduler`
- `/login`
- `/about`
- `/paper`
- `/paper/:name.md` redirects to `/learning/article/:name`
- 404 fallback

菜单、面包屑、页面标题、图标、隐藏菜单项和认证要求由 `libs/routes` 中的 route config 统一维护。不要把这些元信息散落在每个 page 文件中。

### Auth

首版保持当前 localStorage token 方案：

- `auth-token`
- `refresh-token`
- `user-info`

API 请求继续发送 `Authorization: Bearer <token>`。401 或业务认证错误码 `401`、`40101`、`40102`、`40103` 时，统一清理登录态、清理查询缓存并跳转 `/login`。

路由保护在客户端完成。受保护 layout 或 guard 在初始化登录态时显示稳定的 loading 状态，避免未完成初始化时误跳登录页。

### API

`libs/api/client.ts` 封装 axios，保留当前响应语义：

```ts
export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  message: string
  code?: number
  timestamp?: string
  request_id?: string
}
```

API 模块按旧 `frontend-vue/src/api/*` 迁移到 `frontend/libs/api/*`。迁移时去掉 Vue Router、Pinia、Element Plus 直接依赖。页面和业务 feature 通过 TanStack Query 调用 API 函数。

### State

Zustand 管客户端状态：

- auth
- theme
- sidebar
- network status
- notification drawer
- small UI preferences

TanStack Query 管服务端状态：

- 列表
- 详情
- 统计
- 任务状态
- 配置数据
- 报表

不要把 API 响应整体塞进 Zustand。登录、登出和用户切换时必须清理 QueryClient 缓存。

### UI

UI 使用 shadcn/ui + Radix + Tailwind。shadcn 组件通过 CLI 生成到 `components/ui`，组件源码进入仓库。

shadcn 初始化配置：

- style: `new-york`
- base color: `slate`
- CSS variables: enabled
- icon library: lucide
- RSC: yes
- aliases use `@/components`, `@/components/ui`, `@/libs/utils`, `@/hooks`, `@/types`

业务层需要封装：

- `DataTable`
- `PageHeader`
- `ConfirmDialog`
- `AsyncButton`
- `ErrorState`
- `EmptyState`
- `EChartPanel`
- `MarkdownRenderer`

### Forms

表单统一使用 React Hook Form + Zod + shadcn Form。登录、注册、筛选、配置、模型、数据源和系统设置弹窗都按这个方案迁移。

字段级错误优先来自 Zod。API 错误通过 mutation 层 toast 或表单错误映射处理。

### Tables

复杂表格统一使用 TanStack Table + shadcn Table 封装。`DataTable` 必须覆盖：

- loading
- empty
- error
- pagination
- sorting
- filtering
- row actions
- column visibility
- row selection where needed
- server-side pagination where needed

### Theme

暗色模式使用 shadcn CSS variables + next-themes。ECharts、Markdown、Mermaid、Toast、Dialog、表格和代码块都要验证暗色模式下的对比度。

### Markdown and Mermaid

学习中心、论文资源、Markdown 渲染、Mermaid 渲染和 `/paper/:name.md` 兼容重定向都必须保留。

Next Docker 构建必须保留当前前端读取 `docs/` 内容的能力。Markdown/Mermaid 区域可使用 CSS Modules 做局部样式，避免全局样式污染。

### Deployment

`frontend/` 使用 pnpm 和 Next standalone：

- `next.config.ts` 配置 `output: 'standalone'`
- 开发环境使用 Next rewrites 代理 `/api` 到本地 FastAPI
- 生产继续由外层 Nginx 代理 `/api` 和 WebSocket
- Next 容器监听 `3000`
- 切流时 Compose 从旧的 `3000:80` 静态 Nginx 前端改为 Next server runtime

旧 Vue 前端保留在 `frontend-vue/`，不再作为默认 Docker 前端入口。

## 风险

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| UI 库从 Element Plus 切到 shadcn 后组件能力不等价 | 复杂表格、复杂弹窗和表单迁移成本上升 | 先建立 DataTable、Form、Dialog 等通用封装 |
| localStorage token 与 Next SSR 不匹配 | 服务端无法可靠判断登录态 | 首版明确只做客户端保护 |
| 页面数量大，功能遗漏风险高 | 切流后用户遇到缺页或缺操作 | 使用路由清单和功能域清单逐项验收 |
| WebSocket 长连接代理差异 | 通知不可用或重连异常 | 保持协议不变，生产继续 Nginx 代理，Playwright/手工验证连接 |
| Markdown/docs 资源路径遗漏 | 学习中心或论文链接失效 | Docker build 阶段显式复制并验证 docs 读取 |
| 双包管理器并存 | 开发者在错误目录用错命令 | 文档和脚本明确 `frontend` 用 pnpm，`frontend-vue` 用 Yarn |
| 切流 diff 大 | 审查和回滚困难 | 多阶段提交，最终切流单独提交 |

## 回滚

切流后的回滚方式是将部署配置回退到 `frontend-vue/` 的 Vue 静态构建路径，或 revert 最终切流提交。

如果 Next 前端出现阻塞问题，优先回退部署配置到老 Vue 前端镜像或 `frontend-vue/` 构建路径。切流提交必须保持可单独 revert。
