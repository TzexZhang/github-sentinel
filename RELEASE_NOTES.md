# Release Notes

## v0.0.1 - 2026-05-29

GitHub Sentinel 的首个本地版本，完成从项目骨架到可运行轻量服务的基础闭环。

### 新增

- 基于 FastAPI 提供后端服务入口和 OpenAPI 文档。
- 支持 GitHub/Gitee 仓库订阅，订阅参数包括仓库地址、可选访问令牌、秒级订阅间隔和通知通道。
- 支持公开仓库不填写访问令牌；私有仓库或限流场景可填写访问令牌。
- 访问令牌使用 Fernet 加密后写入 SQLite，接口响应只返回 `token_configured` 状态，不暴露明文或密文。
- 提供统一 API 响应结构：`{code, data, success}`，错误提示统一使用中文。
- 提供订阅创建、订阅列表、删除订阅、手动抓取生成报告、报告列表和健康检查接口。
- 支持 `GET /api/reports?within_seconds=秒数` 查询最近指定时间范围内生成的报告。
- 实现 GitHub/Gitee HTTP 抓取适配器，支持从仓库事件接口抓取动态。
- 抓取 Push 事件时，会将每条 commit 拆成独立活动记录，并把 commit message 纳入报告内容。
- 提供 Markdown 报告渲染器，对新入库事件生成中文摘要。
- 提供轻量 Dashboard，支持创建订阅、删除订阅、手动生成报告、查看报告和按时间范围筛选报告。
- 提供启动期 SQLite 轻量迁移，兼容早期订阅表结构。
- 补齐项目源码中类、函数和方法的说明文档。

### 测试与质量

- 使用 pytest 覆盖健康检查、Dashboard、订阅接口、报告筛选、GitHub/Gitee 抓取、手动运行订阅和 Sentinel 编排逻辑。
- 使用 Ruff 做静态检查。
- 当前验证结果：`17 passed`，`ruff check .` 全部通过。

### 已知限制

- 定时调度尚未接入，目前通过 Dashboard 或 `POST /api/subscriptions/{subscription_id}/run` 手动触发抓取。
- 通知发送目前使用空实现，尚未接入邮件、Webhook、Slack 或企业微信等真实通道。
- 抓取逻辑基于平台事件接口完成标准化，尚未针对 Issue、Pull Request、Release 等类型做更细粒度的专用 API 聚合。
