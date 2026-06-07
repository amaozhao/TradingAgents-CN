# 测试环境搭建指南

本文档描述如何用当前仓库中的 Docker Compose 文件验证部署环境。旧版 `docker-compose.hub.yml` / `docker-compose.hub.test.yml` 文件已经不在当前仓库中，现行入口是 `deploy/docker/compose/docker-compose.yml`。

## 当前状态

当前仓库没有提交专用测试 compose 文件。现行可复用的部署栈是 `deploy/docker/compose/docker-compose.yml`，它保持与真实运行方式一致：PostgreSQL、Redis、FastAPI 后端和 Next.js 前端。

需要注意：

- 提交版 compose 定义了固定 `container_name` 和固定 volume name。
- 仅使用 `docker compose -p ...` 不能自动获得完全隔离的容器和数据卷。
- 要与默认开发环境完全并行运行，需要本地不提交的 override 文件覆盖容器名、端口和 volume name。

## 准备配置

本地配置文件固定为 `backend/.env`：

```bash
cp backend/.env.example backend/.env
```

根据测试需要修改其中的 API key、PostgreSQL 和 Redis 配置。后端业务配置由 `app.core.config.Settings` 读取，不使用仓库根目录 `.env`。容器内后端读取挂载后的 `/app/backend/.env`，因此 Docker 场景下 `POSTGRES_HOST` 和 `REDIS_HOST` 应使用 `postgres` / `redis`。

## 启动当前测试栈

确认没有其他同名容器运行后，启动完整栈：

```bash
docker compose \
  --env-file backend/.env \
  -f deploy/docker/compose/docker-compose.yml \
  up -d \
  --build
```

如果默认端口已经被本地服务占用，需要使用本地 compose override 调整端口；不要修改提交版 compose 只为本地临时测试。

当前默认 compose 端口：

| 服务 | 默认端口 | 说明 |
|------|----------|------|
| Frontend | `3000` | Next.js |
| Backend | `8000` | FastAPI |
| PostgreSQL | `5432` | 主数据库 |
| Redis | `6379` | 缓存和通知辅助组件 |
| Redis Commander | `8081` | 可选 management profile |

## 只启动依赖服务

多数后端测试只需要数据库和缓存：

```bash
docker compose \
  --env-file backend/.env \
  -f deploy/docker/compose/docker-compose.yml \
  up -d postgres redis
```

随后运行后端全量严格测试：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml -W error backend -vv
```

## 验证环境

查看容器状态：

```bash
docker compose --env-file backend/.env -f deploy/docker/compose/docker-compose.yml ps
```

查看后端日志：

```bash
docker compose --env-file backend/.env -f deploy/docker/compose/docker-compose.yml logs -f backend
```

访问：

- Web：`http://localhost:3000`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`

## 清理测试环境

停止并删除测试容器和测试数据卷：

```bash
docker compose \
  --env-file backend/.env \
  -f deploy/docker/compose/docker-compose.yml \
  down -v
```

如果只想停止容器但保留数据卷：

```bash
docker compose \
  --env-file backend/.env \
  -f deploy/docker/compose/docker-compose.yml \
  down
```

## 与默认开发环境的关系

| 项目 | 当前提交版 compose | 完全隔离测试栈 |
|------|-------------------|----------------|
| Compose 文件 | `deploy/docker/compose/docker-compose.yml` | 同左 + 本地 override |
| 容器名称 | 固定 `trading-agents-*` | override 中移除或改写 `container_name` |
| 数据卷 | 固定 `trading_agents_postgres_data` / `trading_agents_redis_data` | override 中改写 volume name |
| 端口 | 固定 `3000`、`8000`、`5432`、`6379` | override 中改写宿主机端口 |
| 配置文件 | `backend/.env` | `backend/.env` 或本地 override env 文件 |

当前 compose 文件定义了固定 `container_name` 和固定 volume name，因此默认开发栈和测试栈不能同时完整启动。需要完全并行时，应新增本地不提交的 override 文件，覆盖 `container_name`、宿主机端口和 volume name。

## 推荐测试场景

1. 从空数据库启动，验证注册、配置、股票查询和分析流程。
2. 不配置付费数据源，仅使用免费数据源，验证降级行为。
3. mock LLM 请求，验证分析接口和任务状态流转。
4. 运行后端全量严格测试，确保没有 warning、导入错误或异步资源泄漏。

## 常见问题

### 测试环境可以和默认环境同时运行吗？

当前提交版 compose 使用固定 `container_name`、固定端口和固定 volume name，不能直接同时运行完整栈。需要并行时，用本地 override 覆盖这些值。

### 测试数据会影响默认数据吗？

如果直接使用提交版 compose，volume name 仍是固定的默认值。要做到完全隔离，需要本地 override 覆盖 volume name，或在清理前确认当前 volume 不是要保留的数据。

### 为什么不再使用 `docker-compose.hub.test.yml`？

这些文件已经不在当前仓库。现行 Docker Compose 入口统一在 `deploy/docker/compose/docker-compose.yml`。
