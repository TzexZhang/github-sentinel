# GitHub Sentinel 项目文件说明

本文档用于说明当前项目中的文件夹与文件职责。源码、配置、测试和顶层项目文件逐项说明；`.venv`、`.pytest_cache`、`.ruff_cache`、`__pycache__` 等工具生成目录只说明用途，不展开其内部子文件。

## 系统代码规划与技术栈说明

### 代码规划目标

GitHub Sentinel 的核心目标是把“订阅 GitHub/Gitee 仓库、抓取更新、生成报告、发送通知”拆成可独立演进的模块。当前代码不是把所有逻辑写在路由函数里，而是按职责拆分为 API 层、契约层、服务层、仓储层和数据库层，方便后续逐步补齐真实 GitHub/Gitee API、定时任务、LLM 摘要和多种通知通道。

这种规划优先解决四个问题：

1. **接口稳定**：HTTP 请求和响应由 `schemas/` 中的 Pydantic 模型约束，减少调用方和实现之间的隐式约定。
2. **业务可测试**：核心编排逻辑放在 `services/sentinel.py`，可以用假的代码托管平台客户端、报告渲染器、通知发送器做单元测试。
3. **存储可替换**：数据库读写集中在 `repositories/`，后续从 SQLite 切换到 PostgreSQL 或增加分页查询时，不需要大面积改动 API 层。
4. **外部依赖隔离**：GitHub/Gitee、通知渠道、报告生成都以 `Protocol` 定义接口，当前已提供 HTTP 抓取适配器、Markdown 报告渲染和空通知实现。

### 分层划分思路

```text
HTTP 请求
  -> app/api/routes/        接收请求，声明状态码和响应模型
  -> app/schemas/           校验输入，定义输出契约
  -> app/services/          编排业务流程，连接 GitHub、报告、通知等能力
  -> app/repositories/      封装数据库读写和持久化规则
  -> app/db/                定义 ORM 模型、连接和会话
```

各层职责如下：

| 层级     | 对应目录                | 规划思路                                     |
| ------ | ------------------- | ---------------------------------------- |
| API 层  | `app/api/`          | 只处理 HTTP 语义，例如路由、状态码、依赖注入，不承载复杂业务流程。     |
| 契约层    | `app/schemas/`      | 用 Pydantic V2 明确请求与响应字段、类型、长度、枚举和校验规则。   |
| 服务层    | `app/services/`     | 放置业务用例和外部能力协议，例如 Sentinel Agent 编排、代码托管平台客户端协议、通知协议。 |
| 仓储层    | `app/repositories/` | 统一封装 SQLAlchemy 查询、写入、唯一性冲突和业务级持久化规则。    |
| 数据库层   | `app/db/`           | 定义数据库模型、异步引擎和会话生命周期。                     |
| 核心基础设施 | `app/core/`         | 放置配置和错误处理等跨模块公共能力。                       |

### 文件为什么这样创建

- `app/main.py`：集中创建 FastAPI 应用，注册生命周期、异常处理器和路由。这样测试可以复用 `create_app()`，部署入口也清晰。
- `app/api/deps.py`：把数据库会话依赖命名为 `DbSession`，并集中装配 Sentinel Agent 的抓取、报告和通知实现。
- `app/api/routes/*.py`：按业务资源拆分路由。订阅、报告、健康检查各自独立，后续新增通知通道或调度接口时不会挤在一个文件里。
- `app/core/config.py`：集中处理配置来源。非敏感配置来自 `settings.toml`，敏感配置来自环境变量，避免密钥进入仓库。
- `app/core/errors.py`：统一错误响应结构，失败响应遵循 `{code, data, success}`，中文提示放在 `data.message`，调用方可以根据 `data.error_code` 处理错误。
- `app/db/models.py`：集中定义当前阶段的数据模型，首版体量较小，放在一个文件里可读性更高；订阅模型保存规范化仓库地址、平台、owner、repo、秒级间隔和加密后的 `access_token_encrypted`。
- `app/db/session.py`：集中管理异步数据库连接和会话，避免业务代码直接创建连接。
- `app/repositories/subscriptions.py`：封装订阅创建、列表、删除和重复订阅冲突处理。
- `app/repositories/events.py`：封装仓库事件入库和幂等去重，避免重复 GitHub 事件导致重复报告。
- `app/repositories/reports.py`：封装报告创建和查询，支持按生成时间下限筛选，后续增加分页或按订阅查询时集中修改。
- `app/schemas/subscriptions.py`：定义订阅相关 API 契约，接收必填的 `repository_url`、`interval_seconds` 和可选的 `access_token`、通知通道；平台、owner、repo 由仓库地址解析得到。
- `app/schemas/responses.py`：定义统一接口响应结构和成功/失败响应构造函数，所有 JSON API 返回 `{code, data, success}`。
- `app/schemas/reports.py`：定义报告读取响应契约，保证报告接口返回结构稳定。
- `app/services/github_client.py`：定义仓库活动标准结构、客户端协议和 HTTP 抓取适配器，按 `platform` 区分 GitHub/Gitee，并把远程事件转换为统一活动模型；Push 事件会按每条 commit 拆分，commit message 会进入报告。
- `app/services/reporting.py`：定义报告渲染协议和 Markdown 报告渲染器，当前用于生成本地摘要，后续可以替换为 LLM 摘要。
- `app/services/notifications.py`：定义通知发送协议和空通知发送器，后续可以接入邮件、Webhook、Slack、企业微信等实现。
- `app/services/repository_url.py`：解析 GitHub/Gitee 仓库地址，支持 HTTPS 地址和常见 SSH 地址，并输出统一的 `platform/owner/repo/repository_url`。
- `app/services/tokens.py`：使用 `cryptography` 的 Fernet 对 access_token 加密和解密，写入数据库前不会保留明文 token。
- `app/services/sentinel.py`：放置核心 Agent 编排逻辑，把抓取、去重、报告、通知串成一个可测试用例。
- `tests/conftest.py`：集中定义测试客户端和内存数据库夹具，保证测试之间没有状态污染。
- `tests/test_*.py`：按行为拆分测试文件，分别覆盖健康检查、Dashboard、订阅接口、HTTP 抓取客户端、手动运行接口和 Agent 编排。

### 是否属于业内成熟实践

当前结构属于 Python Web API 项目中常见且成熟的分层方式，尤其适合 FastAPI + SQLAlchemy 的中小型服务。它借鉴了以下工程实践：

- **分层架构**：路由、业务、仓储、数据库职责分离，降低修改影响面。
- **依赖注入**：FastAPI `Depends` 管理请求级数据库会话，服务层通过构造函数注入外部能力。
- **端口与适配器思想**：用 `Protocol` 定义 GitHub、报告、通知这些外部能力的端口，具体适配器后续实现。
- **契约优先**：Pydantic 模型明确 API 输入输出，避免字段含义散落在业务代码中。
- **测试友好设计**：业务编排不绑定真实网络请求，可以用测试替身验证核心流程。

需要说明的是，“成熟实践”不等于唯一方案。对于当前规模，单体模块化架构比微服务更合适，因为它部署简单、调试成本低、模块边界仍然清晰。等到订阅规模、调度吞吐或通知渠道复杂度明显上升后，再评估消息队列、独立 Worker、PostgreSQL、任务调度平台等扩展点更稳妥。

### 当前使用的 Python 技术栈

| 技术                   | 当前用途                                     |
| -------------------- | ---------------------------------------- |
| Python 3.12          | 项目运行语言，使用现代类型标注和异步能力。                    |
| FastAPI              | 构建 HTTP API、路由、依赖注入和 OpenAPI 文档。         |
| Pydantic V2          | 定义请求响应模型、字段校验和 ORM 对象序列化。                |
| pydantic-settings    | 从环境变量加载配置，保护敏感配置不写入仓库。                   |
| cryptography         | 使用 Fernet 对订阅 access_token 做对称加密后再写入 SQLite。 |
| SQLAlchemy 2.x Async | 定义 ORM 模型，执行异步数据库读写。                     |
| aiosqlite            | SQLite 的异步驱动，适合本地开发和首版轻量部署。              |
| Uvicorn              | ASGI 服务运行器，用于启动 FastAPI 应用。              |
| httpx                | 通过 ASGITransport 测试 FastAPI 应用，并在 `HttpRepositoryClient` 中请求 GitHub/Gitee 远程 API。 |
| pytest               | 自动化测试框架。                                 |
| pytest-asyncio       | 支持异步测试函数。                                |
| Ruff                 | Python 静态检查工具，用于发现代码质量问题。                |
| uv                   | Python 版本、虚拟环境、依赖和锁文件管理工具。               |

### 后续演进建议

随着功能逐步细化，可以按以下顺序扩展，而不破坏当前分层：

1. 新增 `app/services/scheduler.py` 或 `app/jobs/`，负责按 `interval_seconds` 调度。
2. 在 `app/services/notifications.py` 协议基础上新增具体通知适配器。
3. 将报告生成从 Markdown 文本渲染扩展为可配置模板或 LLM 摘要。
4. 增加抓取失败审计、报告分页和按订阅筛选。
5. 当数据量增长后，引入 Alembic 管理迁移，并把 SQLite 切换为 PostgreSQL。

## 顶层目录与文件

```text
github-sentinel/
|-- .gitignore
|-- .python-version
|-- .pytest_cache/
|-- .ruff_cache/
|-- .venv/
|-- app/
|-- config/
|-- github_sentinel.db
|-- PROJECT_STRUCTURE.md
|-- pyproject.toml
|-- README.md
|-- tests/
`-- uv.lock
```

| 路径                     | 类型   | 说明                                       |
| ---------------------- | ---- | ---------------------------------------- |
| `.gitignore`           | 文件   | Git 忽略规则，排除 `.env`、虚拟环境、缓存目录、数据库文件和 Python 编译产物。 |
| `.python-version`      | 文件   | 指定项目使用的 Python 版本，当前用于配合 `uv` 固定本地运行时。   |
| `.pytest_cache/`       | 目录   | pytest 测试缓存目录，由测试工具自动生成；不属于业务代码，不展开内部文件。 |
| `.ruff_cache/`         | 目录   | Ruff 静态检查缓存目录，由 Ruff 自动生成；不属于业务代码，不展开内部文件。 |
| `.venv/`               | 目录   | 项目本地虚拟环境，包含 Python 解释器和依赖包；由 `uv sync` 创建，不展开内部文件。 |
| `app/`                 | 目录   | 应用主代码目录，包含 API、配置、数据库、仓储、契约和业务服务。        |
| `config/`              | 目录   | 项目非敏感配置目录。                               |
| `github_sentinel.db`   | 文件   | 本地 SQLite 数据库文件，由应用启动或本地运行时生成；不应作为源代码提交。 |
| `PROJECT_STRUCTURE.md` | 文件   | 当前文档，说明项目目录和文件职责。                        |
| `pyproject.toml`       | 文件   | Python 项目配置，声明 FastAPI、SQLAlchemy、cryptography 等运行依赖，以及 pytest、Ruff 等开发配置。 |
| `README.md`            | 文件   | 项目入口说明文档，包含项目简介、目录概览、常用指令、配置、测试和后续方向。    |
| `tests/`               | 目录   | 自动化测试目录，覆盖健康检查、订阅接口和 Sentinel Agent 编排逻辑。 |
| `uv.lock`              | 文件   | `uv` 依赖锁定文件，用于保证依赖安装结果可复现。               |

## `app/` 应用代码目录

`app/` 是 GitHub Sentinel 的核心应用目录，按职责拆分为 API 层、核心基础设施、数据库层、仓储层、契约层和服务层。

```text
app/
|-- __init__.py
|-- main.py
|-- api/
|-- core/
|-- db/
|-- repositories/
|-- schemas/
`-- services/
```

| 路径                | 类型   | 说明                                       |
| ----------------- | ---- | ---------------------------------------- |
| `app/__init__.py` | 文件   | 标记 `app` 为 Python 包，使应用模块可以被导入。          |
| `app/main.py`     | 文件   | FastAPI 应用入口，定义应用工厂 `create_app()`、生命周期钩子、异常处理器和路由注册。启动时会创建缺失的数据表，便于本地开发和首版运行。 |

## `app/api/` HTTP API 层

`app/api/` 负责 HTTP 请求入口、依赖注入别名和具体路由拆分。该层不直接实现复杂业务逻辑，而是调用仓储层或服务层。

```text
app/api/
|-- __init__.py
|-- deps.py
`-- routes/
```

| 路径                    | 类型   | 说明                                       |
| --------------------- | ---- | ---------------------------------------- |
| `app/api/__init__.py` | 文件   | 标记 `app.api` 为 Python 包。                 |
| `app/api/deps.py`     | 文件   | 定义 API 层依赖别名 `DbSession` 和 `SentinelAgentDep`，统一注入数据库会话和 Sentinel 编排服务。 |

### `app/api/routes/` 路由目录

```text
app/api/routes/
|-- __init__.py
|-- health.py
|-- reports.py
`-- subscriptions.py
```

| 路径                                | 类型   | 说明                                       |
| --------------------------------- | ---- | ---------------------------------------- |
| `app/api/routes/__init__.py`      | 文件   | 标记路由目录为 Python 包。                        |
| `app/api/routes/health.py`        | 文件   | 健康检查路由，提供 `GET /api/health`，用于确认服务和路由注册是否正常。 |
| `app/api/routes/reports.py`       | 文件   | 报告查询路由，提供 `GET /api/reports`，支持通过 `within_seconds` 查询最近指定秒数内的报告。 |
| `app/api/routes/subscriptions.py` | 文件   | 订阅管理路由，提供创建订阅、查询订阅列表、手动抓取生成报告和删除订阅等接口。 |

## `app/core/` 核心基础设施

`app/core/` 存放跨业务模块复用的基础能力，例如配置加载和统一错误结构。

```text
app/core/
|-- __init__.py
|-- config.py
`-- errors.py
```

| 路径                     | 类型   | 说明                                       |
| ---------------------- | ---- | ---------------------------------------- |
| `app/core/__init__.py` | 文件   | 标记 `app.core` 为 Python 包。                |
| `app/core/config.py`   | 文件   | 加载项目配置。默认读取 `config/settings.toml`，也允许通过 `GITHUB_SENTINEL_CONFIG` 覆盖配置文件路径，并通过环境变量注入敏感配置如 `TOKEN_ENCRYPTION_KEY`。 |
| `app/core/errors.py`   | 文件   | 定义业务异常 `ApiError`、请求校验异常处理器和统一失败响应，避免向外暴露内部异常细节。 |

## `app/db/` 数据库层

`app/db/` 负责 SQLAlchemy 基础对象、ORM 模型和异步数据库会话。

```text
app/db/
|-- __init__.py
|-- base.py
|-- models.py
`-- session.py
```

| 路径                   | 类型   | 说明                                       |
| -------------------- | ---- | ---------------------------------------- |
| `app/db/__init__.py` | 文件   | 标记 `app.db` 为 Python 包。                  |
| `app/db/base.py`       | 文件   | 定义 SQLAlchemy Declarative Base，供所有 ORM 模型继承。 |
| `app/db/models.py`     | 文件   | 定义数据库 ORM 模型：`Subscription`、`RepositoryEvent`、`Report`、`NotificationChannel`。这些模型对应订阅、仓库事件、报告和通知通道。 |
| `app/db/migrations.py` | 文件   | 提供轻量启动期兼容迁移，为旧 SQLite 订阅表补充平台、仓库地址、加密 token 字段和秒级间隔字段。 |
| `app/db/session.py`    | 文件   | 创建异步数据库引擎、异步会话工厂，并提供 FastAPI 可注入的 `get_session()`。 |

## `app/repositories/` 仓储层

`app/repositories/` 封装数据库读写细节，API 层和服务层通过仓储函数访问持久化数据。

```text
app/repositories/
|-- __init__.py
|-- events.py
|-- reports.py
`-- subscriptions.py
```

| 路径                                  | 类型   | 说明                                       |
| ----------------------------------- | ---- | ---------------------------------------- |
| `app/repositories/__init__.py`      | 文件   | 标记 `app.repositories` 为 Python 包。        |
| `app/repositories/events.py`        | 文件   | 仓库事件仓储，负责把 GitHub 活动转换为 `RepositoryEvent` 记录，并按 `external_id` 做幂等去重。 |
| `app/repositories/reports.py`       | 文件   | 报告仓储，负责创建报告、按生成时间倒序查询报告列表，并支持按生成时间下限过滤。 |
| `app/repositories/subscriptions.py` | 文件   | 订阅仓储，负责创建订阅、查询订阅列表、删除订阅，并处理重复订阅和订阅不存在等业务错误。 |

## `app/schemas/` 契约层

`app/schemas/` 存放 Pydantic V2 模型，定义 HTTP API 的请求和响应契约。

```text
app/schemas/
|-- __init__.py
|-- reports.py
|-- responses.py
`-- subscriptions.py
```

| 路径                             | 类型   | 说明                                       |
| ------------------------------ | ---- | ---------------------------------------- |
| `app/schemas/__init__.py`      | 文件   | 标记 `app.schemas` 为 Python 包。             |
| `app/schemas/reports.py`       | 文件   | 定义报告响应模型 `ReportRead`，用于序列化报告列表接口返回值。    |
| `app/schemas/responses.py`     | 文件   | 定义统一响应模型 `ApiResponse`，以及 `success_response()`、`error_response()` 构造函数。 |
| `app/schemas/subscriptions.py` | 文件   | 定义订阅创建模型 `SubscriptionCreate` 和订阅读取模型 `SubscriptionRead`。创建订阅时仓库地址和秒级间隔必填，访问令牌和通知通道可选，响应不返回明文或密文 token。 |

## `app/services/` 业务服务层

`app/services/` 存放业务服务协议和核心 Agent 编排逻辑。当前通过 `Protocol` 隔离外部能力，便于后续替换为真实 GitHub API 客户端、LLM 报告生成器和具体通知通道。

```text
app/services/
|-- __init__.py
|-- github_client.py
|-- notifications.py
|-- repository_url.py
|-- reporting.py
|-- tokens.py
`-- sentinel.py
```

| 路径                              | 类型   | 说明                                       |
| ------------------------------- | ---- | ---------------------------------------- |
| `app/services/__init__.py`      | 文件   | 标记 `app.services` 为 Python 包。            |
| `app/services/github_client.py` | 文件   | 定义仓库活动数据结构 `GitHubActivity`、代码托管平台客户端协议 `GitHubClient` 和真实 HTTP 抓取实现 `HttpRepositoryClient`，支持 GitHub/Gitee 事件抓取，并将 Push 事件中的每条 commit message 标准化为报告活动。 |
| `app/services/notifications.py` | 文件   | 定义通知发送协议 `NotificationSender` 和空通知实现 `NullNotificationSender`，用于隔离邮件、Webhook、Slack、企业微信等具体通知实现。 |
| `app/services/repository_url.py` | 文件   | 解析 GitHub/Gitee 仓库地址，支持 HTTPS 和 SSH 风格地址，并统一输出平台、owner、repo 和规范化 URL。 |
| `app/services/reporting.py`     | 文件   | 定义报告渲染协议 `ReportRenderer` 和 `MarkdownReportRenderer`，用于把仓库动态渲染为中文摘要报告。 |
| `app/services/tokens.py`        | 文件   | 负责 access_token 的 Fernet 加密和解密。生产环境应通过 `TOKEN_ENCRYPTION_KEY` 配置稳定密钥。 |
| `app/services/sentinel.py`      | 文件   | 定义核心编排服务 `SentinelAgent` 和运行结果 `SentinelRunResult`。该服务负责按订阅拉取仓库活动、存储新事件、生成报告，并在配置通知通道时发送通知。 |

## `config/` 配置目录

```text
config/
`-- settings.toml
```

| 路径                     | 类型   | 说明                                       |
| ---------------------- | ---- | ---------------------------------------- |
| `config/settings.toml` | 文件   | 默认非敏感配置文件，当前包含应用名称和 SQLite 数据库连接地址。`TOKEN_ENCRYPTION_KEY` 等敏感配置应通过环境变量注入，不写入该文件。 |

## `tests/` 测试目录

`tests/` 存放 pytest 自动化测试，使用 httpx 的 ASGI 测试客户端和内存 SQLite 数据库验证应用行为。

```text
tests/
|-- conftest.py
|-- test_dashboard.py
|-- test_github_client.py
|-- test_health.py
|-- test_reports.py
|-- test_run_subscription_endpoint.py
|-- test_sentinel_agent.py
`-- test_subscriptions.py
```

| 路径                             | 类型   | 说明                                       |
| ------------------------------ | ---- | ---------------------------------------- |
| `tests/conftest.py`            | 文件   | 定义测试客户端夹具。每个测试使用独立的内存 SQLite 数据库，并覆盖生产数据库依赖，避免测试污染本地数据。 |
| `tests/test_dashboard.py`      | 文件   | 验证 Dashboard 页面可访问，并包含订阅、报告和交互所需的核心页面元素。 |
| `tests/test_github_client.py`  | 文件   | 使用 httpx MockTransport 验证 GitHub/Gitee 抓取客户端的请求构造、token 使用和事件标准化逻辑。 |
| `tests/test_health.py`         | 文件   | 验证健康检查接口 `GET /api/health` 返回 `{"status": "ok"}`。 |
| `tests/test_reports.py`        | 文件   | 验证报告查询接口支持通过 `within_seconds` 筛选最近指定时间内生成的报告。 |
| `tests/test_run_subscription_endpoint.py` | 文件 | 验证 `POST /api/subscriptions/{subscription_id}/run` 可以触发抓取、生成报告并返回统一响应。 |
| `tests/test_sentinel_agent.py` | 文件   | 验证 `SentinelAgent` 能拉取活动、去重存储事件、生成报告并发送通知。 |
| `tests/test_subscriptions.py`  | 文件   | 验证订阅创建、订阅列表查询、重复订阅冲突和删除不存在订阅的结构化错误。      |

## 生成目录与缓存说明

以下目录或文件由工具、运行时或本地开发过程生成，不作为业务源码展开说明：

| 路径                      | 说明                                       |
| ----------------------- | ---------------------------------------- |
| `.pytest_cache/`        | pytest 缓存目录，可删除；下次运行测试会重新生成。             |
| `.ruff_cache/`          | Ruff 缓存目录，可删除；下次运行 Ruff 会重新生成。           |
| `.venv/`                | 本地虚拟环境目录，可通过 `uv sync --group dev` 重建。   |
| `app/**/__pycache__/`   | Python 字节码缓存目录，可删除；下次导入模块会重新生成。          |
| `tests/**/__pycache__/` | 测试运行产生的 Python 字节码缓存目录，可删除。              |
| `github_sentinel.db`    | 本地 SQLite 数据库文件，可在需要重置本地数据时删除；应用启动时会按模型创建缺失的数据表。 |
