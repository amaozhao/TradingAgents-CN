# 仓库目录结构

本仓库按运行职责组织目录，避免前端、后端、部署资产和运行生成物混在一起。

## 顶层目录

```text
TradingAgents-CN/
  backend/        FastAPI 后端、tradingagents 包、后端 CLI、后端测试
  frontend/       Vue 3 / Vite 前端应用
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
    docker.env
```

Compose 文件位于 `deploy/docker/compose/`，其中 `build.context` 明确指向仓库根目录，保证镜像仍能复制 `backend/`、`frontend/`、`config/` 和 `docs/`。

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
- `.env.example`
- `.dockerignore`
- `.gitignore`
- `.github/`

新增部署配置时优先放入 `deploy/`，新增运行输出时优先写入 `runtime/`。
