# Git Sentinel

[English](README-EN.md) | 简体中文

Git Sentinel 是一款用于订阅 GitHub/Gitee 仓库、跟踪项目动态、生成 AI 项目报告并推送通知的本地化工具。它把分散的提交、Issue、Pull Request 等仓库事件整理成面向团队阅读的进展报告，适合用于项目周报、版本整理、研发进展同步和私有仓库动态跟踪。

## 目录

- [1. 项目定位](#1-项目定位)
- [2. 核心能力](#2-核心能力)
- [3. 工作流程](#3-工作流程)
- [4. 快速开始](#4-快速开始)
- [5. 配置说明](#5-配置说明)
- [6. API 与界面](#6-api-与界面)
- [7. 开源协议](#7-开源协议)

## 1. 项目定位

Git Sentinel 面向需要持续关注仓库变化的个人开发者、项目管理人员和团队负责人。用户登录后订阅关注的仓库，系统按配置周期获取仓库事件，生成 Markdown 报告，并根据订阅配置决定是否发送通知。

项目当前采用本地账号体系和 SQLite 持久化，适合本地调试、轻量团队部署和私有化运行。

## 2. 核心能力

### 2.1 用户鉴权与数据隔离

- 支持注册、登录、退出登录和修改密码。
- 用户名限制为数字、字母、下划线，长度 2-18 位。
- 密码长度 6-12 位，入库前会加密保存。
- 默认 Cookie 会话有效期为 7 天。
- 首次登录时自动创建默认管理员账号：`admin / 123456`。
- 仓库订阅、报告和通知任务均绑定当前登录用户，新用户不会看到其他用户的数据。

### 2.2 仓库订阅

- 支持订阅 GitHub 和 Gitee 仓库。
- 支持公开仓库；私有仓库可配置访问令牌。
- 访问令牌加密保存，页面和接口不会返回明文。
- 支持创建、查看、修改和删除订阅。
- 支持按每个订阅配置独立检查间隔，不同仓库可使用不同运行周期。
- 支持订阅级通知配置：不通知、邮箱 SMTP、企业微信通知。

### 2.3 仓库动态获取

- 按订阅周期获取仓库事件。
- 汇总 Push、Issue、Pull Request 等项目动态。
- 识别一次 Push 中的多条提交说明。
- 为报告生成和通知投递提供统一数据来源。

### 2.4 报告生成

- 支持按指定日期范围生成报告。
- 支持手动生成报告，并可选择是否发送通知。
- 手动生成报告并勾选发送通知时，会为本次操作创建新的通知任务；即使复用既有历史报告且没有新事件，也会再次进入通知发送流程。
- 同一订阅、同一日期范围重复生成时会更新既有报告，减少重复堆积。
- 报告正文以 Markdown 保存，便于阅读、复制和通知转换。
- 报告列表按生成时间倒序展示，最新报告排在最上方。
- 报告内容以业务功能和结果为导向，合并相似改动，减少重复描述和低价值代码细节。
- 未配置 LLM 密钥时，会回退生成基础 Markdown 报告。

### 2.5 报告管理

- 支持在 Dashboard 中查看报告列表和报告正文。
- 支持按订阅和时间范围查询报告。
- 支持批量勾选报告并物理删除。
- 删除操作仅影响当前登录用户拥有的报告。

### 2.6 通知系统

- 订阅可选择“不通知”“邮箱 SMTP”“企业微信通知”。
- 报告生成后按订阅配置创建通知任务。
- 定时任务会对同一报告和同一通知通道保持去重；手动勾选发送通知时不复用旧通知任务。
- Notification Worker 统一扫描待发送任务并投递通知。
- Worker 每轮默认处理 50 条任务，避免大量报告时单轮处理过重。
- SMTP 通知会把 Markdown 报告转换为 HTML 邮件正文。
- 企业微信通知发送完整报告内容，内容超过限制时自动拆分为多条文本消息。
- 通知任务记录发送状态、失败原因和重试时间，便于排查。

### 2.7 可视化界面

- 基于 Gradio 提供 Dashboard。
- 默认先展示登录/注册入口，登录后进入主界面。
- 支持仓库订阅、报告查看、报告管理和用户管理。
- 用户管理支持修改密码和退出登录。

## 3. 工作流程

```text
注册或登录
  -> 创建仓库订阅
  -> 配置访问令牌、检查间隔和通知类型
  -> 定时或手动获取仓库动态
  -> 生成项目进展报告
  -> 查看、管理或删除报告
  -> 按订阅配置发送 SMTP 或企业微信通知
```

## 4. 快速开始

### 4.1 安装依赖

项目使用 `uv` 管理 Python 版本、虚拟环境和依赖。

```powershell
uv sync --group dev
```

### 4.2 启动服务

本地开发用以下命令启动:

```powershell
uv run python scripts/dev.py
```

> 自定义端口: `uv run python scripts/dev.py --port 8001`

> 💡 **关于热重载**:本项目不使用 uvicorn 的 `--reload`——它在 Windows 上会卡死在 `Waiting for connections to close`(uvicorn 已知缺陷)。改完代码后请手动停止(Ctrl+C)再重新运行上述命令。`scripts/dev.py` 已内置优雅关闭超时(`--timeout-graceful-shutdown 3`),正常情况下按一次 Ctrl+C 即可停止;若残留连接导致短暂等待,连按两次 Ctrl+C 可立即强退。

启动后访问:

| 页面/接口 | 地址 |
| --- | --- |
| Dashboard | `http://127.0.0.1:8000/` |
| API 文档 | `http://127.0.0.1:8000/docs` |
| 健康检查 | `http://127.0.0.1:8000/api/health` |

默认管理员账号：

| 用户名 | 密码 |
| --- | --- |
| `admin` | `123456` |

### 4.3 数据库

默认 SQLite 数据库路径为 `./data/github_sentinel.db`。首次启动时，应用会自动创建数据库文件和缺失的数据表。

Docker 部署时，`docker-compose.yml` 会将宿主机 `./data` 挂载到容器 `/app/data`，用于持久化数据库文件。

> ℹ️ **关于 `-shm` / `-wal` 辅助文件**
>
> 启动服务后，`data/` 目录下除主库 `github_sentinel.db` 外，还会自动出现两个配套文件，这是 SQLite **WAL（预写日志）模式**的正常产物，并非冗余或垃圾文件：
>
> | 文件 | 作用 |
> |------|------|
> | `github_sentinel.db` | 主数据库，存放所有正式数据（**不可删除**） |
> | `github_sentinel.db-wal` | 预写日志。写入先落盘到这里，再异步合并回主库，提升并发性能 |
> | `github_sentinel.db-shm` | 共享内存索引。协调多连接并发读写 WAL |
>
> 项目启用 WAL 模式（`app/db/session.py` 中 `PRAGMA journal_mode=WAL`）是为了规避 SQLite 默认模式下的 `database is locked` 并发写冲突。这三个文件是配套的一组，**运行时缺一不可**。
>
> **注意**：如需清理 `-shm` / `-wal`，必须**先停止服务**让 SQLite 完成 checkpoint（将 WAL 数据合并回主库），否则可能丢失尚未落盘的写入；且下次启动服务会因 WAL 模式再次自动生成这两个文件。日常使用建议保持现状，它们已被 `.gitignore` 忽略，不影响版本库。

## 5. 配置说明

项目默认读取 `config/settings.toml` 中的非敏感配置。敏感信息建议通过环境变量注入，不要写入配置文件或提交到仓库。

| 配置项 | 作用 |
| --- | --- |
| `DATABASE_URL` | 数据库连接地址 |
| `TOKEN_ENCRYPTION_KEY` | 仓库访问令牌加密密钥 |
| `GITHUB_SENTINEL_CONFIG` | 自定义配置文件路径 |
| `LLM_API_KEY` | LLM 服务访问密钥，未配置时回退为基础 Markdown 报告 |
| `LLM_PROVIDER` | LLM 服务提供方，默认 `zhipu`，可配置 `gemini` |
| `LLM_MODEL` | LLM 模型名称 |
| `LLM_BASE_URL` | OpenAI-compatible 接口地址 |
| `AUTH_COOKIE_NAME` | 登录 Cookie 名称 |
| `AUTH_SESSION_DAYS` | 登录会话有效天数，默认 7 天 |
| `ADMIN_USERNAME` | 默认管理员用户名 |
| `ADMIN_PASSWORD` | 默认管理员密码 |
| `NOTIFICATION_SMTP_HOST` | SMTP 服务地址 |
| `NOTIFICATION_SMTP_PORT` | SMTP 服务端口 |
| `NOTIFICATION_SMTP_USERNAME` | SMTP 用户名 |
| `NOTIFICATION_SMTP_PASSWORD` | SMTP 密码 |
| `NOTIFICATION_SMTP_FROM_EMAIL` | SMTP 发件人地址 |
| `NOTIFICATION_WECOM_CORP_ID` | 企业微信 CorpID |
| `NOTIFICATION_WECOM_AGENT_ID` | 企业微信 AgentId |
| `NOTIFICATION_WECOM_SECRET` | 企业微信应用 Secret |
| `NOTIFICATION_WECOM_TO_USER` | 企业微信默认接收人 |
| `NOTIFICATION_WORKER_ENABLED` | 是否启用通知 Worker |
| `SCHEDULER_ENABLED` | 是否启用订阅调度器 |

生产环境建议显式配置 `TOKEN_ENCRYPTION_KEY`。可使用以下命令生成 Fernet key：

```powershell
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 6. API 与界面

系统同时提供 FastAPI 接口和 Gradio Dashboard。日常使用以 Dashboard 为主；自动化集成可使用 `/api/auth`、`/api/subscriptions`、`/api/reports` 等接口。

主要模块：

| 模块 | 能力 |
| --- | --- |
| 认证 | 注册、登录、退出登录、修改密码、查询当前用户 |
| 仓库订阅 | 创建、查看、修改、删除订阅，配置检查间隔和通知类型 |
| 报告生成 | 按日期范围生成报告，支持生成后通知 |
| 报告管理 | 查看报告列表、预览正文、批量删除 |
| 通知投递 | SMTP 邮件、企业微信通知、任务状态记录 |
| 运行状态 | 健康检查、运行时信息 |

## 7. 开源协议

本项目采用 MIT License 开源，详见 [LICENSE](LICENSE)。
