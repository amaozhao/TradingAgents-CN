# 仓库目录结构

本仓库按运行职责组织目录，避免前端、后端、部署资产和运行生成物混在一起。

## 顶层目录

```text
TradingAgents-CN/
  backend/        FastAPI 后端、trader 包、后端 CLI、后端测试
  frontend/       Next.js App Router + React 前端
  frontend-vue/   Vue 3 / Vite 旧前端回滚基线
  deploy/         Docker、Nginx、部署环境样例
  config/         可版本控制的默认配置
  docs/           项目文档
  runtime/        本地运行数据、日志、缓存和导出产物（不入库）
```

## 部署资产

Docker 和 Nginx 相关文件统一放在 `deploy/`：

```text
deploy/
  docker/
    backend.Dockerfile
    frontend.Dockerfile
    compose/
      docker-compose.yml
      docker-compose.hub.nginx.yml
      docker-compose.hub.nginx.arm.yml
    nginx/
      frontend.conf
      reverse-proxy.conf
  env/
    docker.env        旧 Docker 环境样例；现行 compose 入口统一读取 backend/.env
```

Compose 文件位于 `deploy/docker/compose/`，其中 `build.context` 明确指向仓库根目录，保证镜像仍能复制 `backend/`、`frontend/`、`config/` 和 `docs/`。旧 Vue 前端保留在 `frontend-vue/` 作为回滚基线。

## 后端应用结构

后端内部按职责拆分，避免把配置、ORM、DTO 和数据库访问层混在一起：

```text
backend/app/
  core/      全局配置、运行时资源、数据库/Redis 客户端和 SQLAlchemy session 生命周期
  models/    SQLAlchemy ORM 表模型
  schemas/   Pydantic 请求/响应 DTO
  db/        PostgreSQL 查询、写入和文档存储兼容层
```

迁移文件属于 Alembic，位置为 `backend/alembic/`。`app/db/` 不承担迁移目录职责。

后端配置统一通过 `app.core.config.Settings` 从 `backend/.env` 读取；不要在仓库根目录新增 `.env`，也不要在业务代码里新增分散的环境变量解析。

## 运行生成物

本地运行时产生的数据统一放到 `runtime/`，包括：

- `runtime/data/`
- `runtime/logs/`
- `runtime/cache/`
- `runtime/exports/`
- `runtime/reports/`

这些内容由 `.gitignore` 忽略，不应提交到版本库。

## 保留在根目录的文件

根目录只保留项目入口和跨应用元数据，例如：

- `README.md`
- `LICENSE`
- `VERSION`
- `.dockerignore`
- `.gitignore`
- `.github/`

新增部署配置时优先放入 `deploy/`，新增运行输出时优先写入 `runtime/`。

后端本地环境变量模板位于 `backend/.env.example`，实际本地配置文件为
`backend/.env`，该文件由 `.gitignore` 忽略，不应提交。
