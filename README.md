# GitHub Sentinel

GitHub Sentinel 是一款基于 FastAPI 的开源工具类 AI Agent 服务，用于通过仓库地址订阅 GitHub/Gitee 仓库、按需加密保存访问令牌、采集仓库动态、生成摘要报告，并按自定义秒级间隔发送通知。

## 架构概览

- FastAPI 负责 HTTP API，并为后续 Dashboard 页面提供服务入口。
- Pydantic V2 负责请求、响应和错误结构的强类型契约。
- async SQLAlchemy 负责通过 SQLite 存储订阅、加密后的访问令牌、仓库事件、报告和通知通道。
- cryptography 负责在 access_token 写入 SQLite 前进行 Fernet 对称加密，API 响应不会返回明文或密文 token。
- GitHub/Gitee 抓取、报告渲染、通知发送通过服务协议隔离，当前已提供 HTTP 抓取适配器、Markdown 摘要渲染器和空通知发送器。

## 项目目录说明

```text
github-sentinel/
├── app/
│   ├── api/                 # HTTP API 层：路由、依赖注入和请求入口
│   │   └── routes/          # 按业务资源拆分的 FastAPI Router
│   ├── core/                # 核心基础设施：配置加载、统一错误结构
│   ├── db/                  # 数据库层：SQLAlchemy Base、模型、异步会话
│   ├── repositories/        # 仓储层：封装订阅、仓库事件、报告等持久化操作
│   ├── schemas/             # Pydantic 契约：请求、响应和对外数据结构
│   ├── services/            # 业务服务层：GitHub/Gitee 抓取、报告生成、通知、Agent 编排
│   └── main.py              # FastAPI 应用工厂、生命周期和路由注册
├── config/
│   └── settings.toml        # 非敏感默认配置，敏感配置通过环境变量注入
├── tests/                   # pytest 测试：API、Dashboard、仓储和 Agent 编排行为
├── pyproject.toml           # 项目元数据、依赖、pytest 与 Ruff 配置
├── uv.lock                  # uv 锁定文件，保证依赖版本可复现
└── README.md                # 项目说明文档
```

核心依赖方向为 `api -> repositories/services -> db`。`services` 中使用 `Protocol` 定义代码托管平台客户端、报告渲染器和通知发送器，便于后续替换真实 GitHub/Gitee API、LLM 摘要或 Slack/Webhook 等通知通道。

## 本地开发

本项目使用 `uv` 管理 Python 版本、虚拟环境和依赖，不依赖系统 Python。

```powershell
uv sync --group dev
uv run python -m uvicorn app.main:create_app --factory --reload
```

## 常用指令说明

| 指令 | 作用 |
| ---- | ---- |
| `uv sync --group dev` | 根据 `pyproject.toml` 和 `uv.lock` 创建或更新本地虚拟环境，并安装运行与开发依赖。 |
| `uv run python -m uvicorn app.main:create_app --factory --reload` | 以应用工厂模式启动 FastAPI 服务，`--reload` 会在代码变更后自动重启，适合本地开发。使用 `python -m uvicorn` 可以避开 Windows 下 `uvicorn.exe` 脚本入口的路径解析问题。 |
| `$env:TOKEN_ENCRYPTION_KEY="..."` | 设置 Fernet 加密密钥，用于加密订阅 access_token。生产环境必须显式配置。 |
| `uv run pytest` | 运行 `tests/` 下的自动化测试，验证 API、Dashboard、仓储层和 Agent 编排逻辑。 |
| `uv run ruff check .` | 运行 Ruff 静态检查，发现未使用导入、格式问题和潜在代码质量问题。 |

如果执行 `uv run uvicorn app.main:create_app --factory --reload` 时出现 `Failed to canonicalize script path`，请改用上面的 `uv run python -m uvicorn ...`。该错误来自 `uvicorn.exe` 脚本入口的路径规范化失败，服务代码本身可以正常运行。

## 配置

项目默认读取正式配置文件 `config/settings.toml`。敏感配置不要写入仓库，应通过环境变量注入。

生产环境必须配置 `TOKEN_ENCRYPTION_KEY`。该值需要是 Fernet key，可用下面命令生成：

```powershell
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:TOKEN_ENCRYPTION_KEY="上一步生成的 key"
```

如果未设置 `TOKEN_ENCRYPTION_KEY`，项目会使用仅适合本地开发的默认密钥，方便测试和演示；不要在生产环境依赖默认密钥。

可用配置项：

- `APP_NAME`：覆盖服务名称。
- `DATABASE_URL`：覆盖 SQLite 数据库连接地址。
- `TOKEN_ENCRYPTION_KEY`：Fernet 加密密钥，用于加密写入 SQLite 的订阅 access_token。
- `GITHUB_SENTINEL_CONFIG`：覆盖默认配置文件路径。

## 订阅方式

当前订阅接口使用统一方案：调用方需要提供仓库地址和订阅间隔。公开仓库可以不填访问令牌；私有仓库或需要提高 API 限流额度时应填写访问令牌。

```json
{
  "repository_url": "https://github.com/encode/httpx",
  "access_token": "ghp_your_token",
  "interval_seconds": 60,
  "notification_channel": "team-webhook"
}
```

公开仓库也可以省略 `access_token`：

```json
{
  "repository_url": "https://github.com/encode/httpx",
  "interval_seconds": 60
}
```

后端会自动解析：

- `platform`：`github` 或 `gitee`
- `owner`：仓库所有者
- `repo`：仓库名称
- `repository_url`：规范化后的仓库地址

如果提供 `access_token`，后端会在写入 SQLite 前加密保存到 `access_token_encrypted`。查询订阅时只返回 `token_configured: true/false`，不会返回明文 token 或密文 token。

## 接口响应格式

后端 JSON 接口统一返回以下结构：

```json
{
  "code": 200,
  "data": {},
  "success": true
}
```

- `code`：HTTP 语义状态码，例如 `200`、`201`、`404`、`422`。
- `data`：成功时为业务数据，无数据场景为 `null`。
- `success`：请求是否成功。

失败响应中的提示信息统一放在 `data.message`，并使用中文：

```json
{
  "code": 409,
  "data": {
    "message": "该仓库已订阅。",
    "error_code": "subscription_conflict"
  },
  "success": false
}
```

## 运行测试

```powershell
uv run pytest
uv run ruff check .
```

## 当前首版能力

- 健康检查接口：`GET /api/health`
- 创建订阅：`POST /api/subscriptions`
- 查询订阅列表：`GET /api/subscriptions`
- 手动抓取并生成报告：`POST /api/subscriptions/{subscription_id}/run`
- 删除订阅：`DELETE /api/subscriptions/{subscription_id}`
- 查询报告列表：`GET /api/reports`，可通过 `within_seconds` 查询最近指定秒数内的报告，例如 `GET /api/reports?within_seconds=86400`。
- 轻量 Dashboard：`GET /`，支持创建订阅、删除订阅、立即生成报告、按时间范围筛选报告和查看报告。
- 订阅契约支持通过 GitHub/Gitee 仓库地址自动识别平台，支持 access_token 加密入库，支持秒级 `interval_seconds` 订阅间隔。
- 抓取逻辑支持 GitHub 仓库 Events API 与 Gitee 仓库 Events API，访问令牌可选；私有仓库或限流场景可配置 token。
- 抓取 Push 事件时会把每条 commit 拆成独立仓库动态，commit message 会作为报告内容的一部分展示。
- 报告生成使用本地 Markdown 模板，对新入库事件进行摘要；重复事件会通过 `external_id` 幂等去重。

## 后续开发方向

1. 增加定时调度任务，按订阅的 `interval_seconds` 节奏自动抓取更新。
2. 扩展 GitHub/Gitee 抓取维度，按 Issue、Pull Request、Release、Commit 等类型提供更细粒度摘要。
3. 将报告生成从 Markdown 模板扩展为 LLM 摘要或可配置模板。
4. 接入邮件、Webhook、Slack、企业微信等真实通知渠道。
5. 增加报告分页、按订阅筛选和抓取失败审计记录。
