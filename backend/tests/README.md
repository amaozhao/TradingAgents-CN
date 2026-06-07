# 后端测试说明

本文档描述当前 `backend/tests/` 的真实结构和推荐运行方式。

## 目录结构

```text
backend/tests/
  app/          FastAPI、服务层、schemas、数据库访问层和运行时行为测试
  cli/          后端 CLI 入口和命令行为测试
  regression/   已修复问题的回归测试
  tools/        代码结构和审计类测试
  trader/       核心交易分析包测试
  conftest.py   pytest 夹具、事件循环和运行后清理逻辑
```

部分历史测试辅助代码保留在 `backend/support/`，当前 pytest 入口以 `backend/tests/` 下的 wrapper 和回归测试为准。

## 推荐命令

后端全量严格测试：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml -W error backend -vv
```

Ruff 检查：

```bash
conda run --no-capture-output -n trader ruff check backend
conda run --no-capture-output -n trader ruff format --check backend
```

只在定位问题时运行子集：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml backend/tests/app -vv
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml backend/tests/regression -vv
```

如果要对外声明“全量测试通过”，必须运行完整 `backend` 测试范围，不使用 `-k`、`--ignore`、`--deselect` 或只跑某个子目录。测试自身定义的 `skipped` 不等同于手动 deselect。

## 环境配置

后端测试读取 `backend/.env`，配置入口为 `app.core.config.Settings`。

```bash
cp backend/.env.example backend/.env
```

测试代码不要直接新增分散的 `os.getenv` 配置读取。需要新配置时，先添加到 `app.core.config.Settings`，再在测试中通过 `settings` 使用。

## 数据库和网络

- PostgreSQL 和 Redis 使用当前 `backend/.env` 配置。
- 免费数据源和普通外部网络请求可以在集成测试中真实请求。
- LLM 请求应在测试中 mock，避免成本、速率限制和结果不稳定。
- 需要依赖服务时，可先启动：

```bash
docker compose --env-file backend/.env -f deploy/docker/compose/docker-compose.yml up -d postgres redis
```

## 新增测试规范

- import 语句必须位于 module 层顶部。
- 测试函数用 `assert` 表达预期，不要通过 `return True` / `return False` 表达结果。
- 异步网络和数据库逻辑使用异步客户端或 pytest 异步测试，不新增同步阻塞请求。
- 涉及请求/响应结构时，优先校验 `app.schemas` 中的 Pydantic DTO。
- 涉及数据库表结构时，优先校验 `app.models` 中的 SQLAlchemy ORM 模型。
- 回归测试放在 `backend/tests/regression/`，文件名说明修复过的问题。

## 故障排除

- 导入失败：检查包路径、module 顶部 import 和 `backend/pyproject.toml` 的 pytest 配置。
- warning 变成失败：全量严格命令使用 `-W error`，需要修复根因，不要过滤。
- 数据库失败：检查 Docker 服务、`backend/.env` 和 Alembic 迁移状态。
- 网络失败：区分免费数据源不可用、LLM mock 缺失和本地代理配置问题。
