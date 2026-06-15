# 数据库与缓存配置指南

本文档描述当前后端真实使用的 PostgreSQL、Redis、配置加载和迁移职责。

## 当前架构

后端以 PostgreSQL 作为主持久化存储，Redis 作为缓存、会话和实时通知辅助组件。

```text
backend/app/
  core/
    config.py       pydantic-settings 配置入口，读取 backend/.env
    session.py      SQLAlchemy async engine 和 session 生命周期
    database.py     PostgreSQL 文档存储客户端和 Redis 连接生命周期
    redis.py        Redis 客户端封装
  models/           SQLAlchemy ORM 表模型
  schemas/          Pydantic 请求/响应 DTO
  db/               PostgreSQL 查询、写入和文档存储兼容层
  db/store/         Mongo-like 文档接口，底层写入 PostgreSQL JSONB
backend/alembic/    Alembic 迁移脚本
```

职责边界：

- `app.models` 只放 SQLAlchemy ORM 表模型。
- `app.schemas` 只放 Pydantic 请求/响应 DTO。
- `app.db` 是数据库访问层，不放迁移脚本。
- 迁移属于 Alembic，统一放在 `backend/alembic/`。
- 配置统一通过 `app.core.config.Settings` 加载，不在业务代码里新增分散的 `os.getenv` 读取。

## 配置来源

本地后端配置文件固定为 `backend/.env`：

```bash
cp backend/.env.example backend/.env
```

后端启动时由 `app.core.config.Settings` 读取该文件。不要在仓库根目录新增 `.env`，也不要让业务代码绕过 `Settings` 手动解析环境变量。

关键数据库配置示例：

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=trading_agents_cn
POSTGRES_POOL_SIZE=3
POSTGRES_MAX_OVERFLOW=2
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_RECYCLE=1800
POSTGRES_ECHO=false
POSTGRES_DUAL_WRITE_ENABLED=true
POSTGRES_READ_ENABLED=true
POSTGRES_DUAL_WRITE_FAIL_OPEN=true
SYNC_STOCK_BASICS_ENABLED=true

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=trading_agents123
REDIS_DB=0
```

### PostgreSQL 连接池 sizing

本地开发推荐从较小连接池开始：

```env
POSTGRES_POOL_SIZE=3
POSTGRES_MAX_OVERFLOW=2
POSTGRES_POOL_TIMEOUT=30
```

这些值不是全局上限，而是每个后端进程、worker 进程和 event loop 对应 SQLAlchemy async engine 的上限。按默认 `pool_size + max_overflow` 计算，上面的本地配置是每个 engine 最多 5 个连接。

生产或压测环境需要按实际部署计算：

```text
总连接预算 >= (后端进程数 + worker 进程数 + 其他长驻进程数) * (POSTGRES_POOL_SIZE + POSTGRES_MAX_OVERFLOW) + 运维/迁移保留连接
```

不要只通过调大 PostgreSQL `max_connections` 掩盖应用侧连接池放大问题。长驻 Web/Worker 运行时应优先使用 async DB 路径，并避免通过同步 facade 创建额外 event loop 和连接池。

如果后端也运行在 Docker Compose 容器内，应把连接主机名改为服务名：

```env
POSTGRES_HOST=postgres
REDIS_HOST=redis
```

Docker Compose 中：

- `postgres`、`redis` 和 `backend` 服务都读取 `backend/.env`。
- `backend` 服务会把宿主机 `backend/.env` 挂载到容器内 `/app/backend/.env`，供 `app.core.config.Settings` 读取。
- 容器部署时，`backend/.env` 中的 `POSTGRES_HOST` 和 `REDIS_HOST` 应使用 compose 服务名 `postgres` / `redis`。

## 启动本地依赖服务

只启动 PostgreSQL 和 Redis：

```bash
docker compose --env-file backend/.env -f deploy/docker/compose/docker-compose.yml up -d postgres redis
```

启动完整容器栈：

```bash
docker compose --env-file backend/.env -f deploy/docker/compose/docker-compose.yml up -d
```

当前 compose 使用：

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| PostgreSQL | `postgres:alpine` | `5432` | 主数据库 |
| Redis | `redis:alpine` | `6379` | 缓存和通知辅助组件 |
| Backend | 本地构建 | `8000` | FastAPI |
| Frontend | 本地构建 | `3000` | Next.js |
| Redis Commander | `ghcr.io/joeferner/redis-commander:latest` | `8081` | 可选 management profile |

启用 Redis Commander：

```bash
docker compose --env-file backend/.env -f deploy/docker/compose/docker-compose.yml --profile management up -d redis-commander
```

## 数据库迁移

迁移由 Alembic 管理，从 `backend/` 目录执行：

```bash
cd backend
conda run --no-capture-output -n trader alembic upgrade head
```

新增或修改 ORM 表模型后，再生成迁移：

```bash
cd backend
conda run --no-capture-output -n trader alembic revision --autogenerate -m "describe_change"
```

生成迁移前需要确认：

- 表模型在 `backend/app/models/`。
- `backend/alembic/env.py` 能导入 `app.models.table` 和 `Base.metadata`。
- `backend/.env` 指向正确的 PostgreSQL 实例。

## 启动后端和前端

本地开发推荐：

```bash
# 终端 1：后端
./backend/scripts/dev/start/backend.sh

# 终端 2：前端
cd frontend
pnpm install
pnpm dev --hostname 0.0.0.0 --port 3000
```

访问地址：

- Next.js Web：`http://localhost:3000`
- FastAPI 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`

## 验证命令

后端全量严格测试：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml -W error backend -vv
```

后端 Ruff 检查：

```bash
conda run --no-capture-output -n trader ruff check backend
conda run --no-capture-output -n trader ruff format --check backend
```

如果要声明“全量测试通过”，不要使用 `-k`、`--ignore`、自定义 deselect 或只跑某个子目录。

## 排查要点

- 后端导入错误：优先检查导入是否位于 module 顶部，以及 `backend/.env` 是否存在。
- 数据库连接失败：检查 `POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_PASSWORD` 是否与当前运行方式一致。
- Redis 认证失败：检查 `REDIS_PASSWORD` 是否与 compose 中 Redis 命令一致。
- 迁移未生效：从 `backend/` 目录运行 Alembic，并确认连接的是目标数据库。
- 接口 DTO 不清晰：请求和响应结构应在 `app.schemas` 中定义，不要放回 ORM 模型目录。
