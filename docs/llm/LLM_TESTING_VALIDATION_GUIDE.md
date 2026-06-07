# LLM 适配器测试指南

本文档描述当前后端新增或修改 LLM provider 后的验证方式。测试必须符合后端现行结构：配置通过 `app.core.config.Settings` 读取，测试文件放在分层目录中，LLM 真实请求默认 mock。

## 配置入口

本地配置文件固定为 `backend/.env`：

```bash
cp backend/.env.example backend/.env
```

新增 provider 配置时：

- 先在 `backend/app/core/config.py` 的 `Settings` 中定义字段。
- 再在 `backend/.env.example` 中补充示例。
- 业务代码和测试都从 `app.core.config.settings` 读取配置。
- 不要在测试或业务代码里新增分散的环境变量解析。

示例：

```python
from app.core.config import settings


def test_qianfan_api_key_config() -> None:
    api_key = settings.QIANFAN_API_KEY
    assert api_key
    assert api_key.startswith("bce-v3/")
```

## 测试位置

按被测对象放置测试：

```text
backend/tests/trader/llm/adapters/<provider>/test.py
backend/tests/trader/llm/clients/<provider>/test.py
backend/tests/trader/llm/clients/keys/test.py
backend/tests/trader/llm/clients/providers/test.py
backend/tests/trader/llm/clients/models/test.py
backend/tests/trader/agents/utils/google/test.py
```

不要新增 `backend/tests/test_provider.py` 这类扁平文件。当前测试树使用分层 wrapper 结构。

## 基础测试模板

```python
from unittest.mock import MagicMock

from app.core.config import settings
from trader.llm.clients import factory


def test_provider_key_is_configurable() -> None:
    assert hasattr(settings, "QIANFAN_API_KEY")


def test_provider_client_creation_uses_mocked_transport(monkeypatch) -> None:
    fake_client = MagicMock()
    monkeypatch.setattr(
        factory,
        "create_llm_client",
        lambda provider, model, **kwargs: fake_client,
    )

    client = factory.create_llm_client("qianfan", "ernie-3.5-8k")
    assert client is fake_client
```

测试要求：

- import 语句必须位于 module 顶部。
- 测试函数使用 `assert`，不要用 `return True` / `return False` 表达结果。
- LLM 请求必须 mock，避免真实扣费、速率限制和不稳定响应。
- 免费数据源和普通外部网络请求可在集成测试中真实请求。
- 异步网络逻辑使用异步客户端和 pytest 异步测试，不新增同步阻塞请求。

## Web 集成验证

当前主 Web 是 `frontend/` 的 Next.js，不再为新功能新增 Streamlit Web 测试。

后端侧验证 provider 配置接口：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml \
  backend/tests/app/routers/config \
  backend/tests/app/services/config \
  backend/tests/app/schemas/config \
  -vv
```

前端侧使用 Next.js 测试命令：

```bash
cd frontend
pnpm test
pnpm lint
pnpm type-check
```

## 推荐验证命令

LLM client/provider 子集：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml \
  backend/tests/trader/llm/clients \
  backend/tests/trader/llm/adapters \
  -vv
```

Google 相关子集：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml \
  backend/tests/trader/llm/clients/google \
  backend/tests/trader/agents/utils/google \
  backend/tests/trader/flows/news/google \
  -vv
```

后端全量严格测试：

```bash
conda run --no-capture-output -n trader python -m pytest -c backend/pyproject.toml -W error backend -vv
```

Ruff 检查：

```bash
conda run --no-capture-output -n trader ruff check backend
conda run --no-capture-output -n trader ruff format --check backend
```

对外声明“全量测试通过”时，必须运行完整 `backend` 范围，不使用 `-k`、`--ignore`、`--deselect` 或只跑某个子目录。

## 验证清单

- `Settings` 中存在 provider 所需字段。
- `.env.example` 中有对应示例。
- provider key 不会出现在日志或错误响应中。
- client factory 能创建 provider client。
- adapter 层对模型名、base URL、超时和错误映射有测试。
- LLM 实际调用路径已 mock。
- Web 配置接口和 Pydantic schema 测试覆盖新增字段。
- 全量严格测试和 Ruff 检查通过。

## 常见问题

### API key 读取不到

先确认 `backend/.env` 存在，再检查字段是否已经定义在 `app.core.config.Settings` 中。不要在单个测试里临时解析根目录 `.env`。

### LLM 测试不稳定

真实 LLM 请求不应进入常规测试。用 monkeypatch、fixture 或测试专用 fake client 固定响应。

### Provider 不出现在 Web 配置中

检查后端配置 schema、配置服务和前端 provider 列表是否同时更新。后端至少运行 `backend/tests/app/routers/config`、`backend/tests/app/services/config` 和 `backend/tests/app/schemas/config`。
