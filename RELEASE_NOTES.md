# GitHub Sentinel Release Notes

## v0.0.1 - 2026-05-29

`v0.0.1` 是 GitHub Sentinel 的首个可运行版本，完成了仓库订阅、访问令牌加密存储、仓库动态抓取、报告生成、统一接口响应和轻量 Dashboard 的基础闭环。

## 版本亮点

- 支持通过仓库地址订阅 GitHub/Gitee 仓库。
- 支持公开仓库不填写 `access_token`，私有仓库可填写访问令牌。
- `access_token` 写入 SQLite 前使用 Fernet 加密，接口不会返回明文或密文。
- 支持手动触发仓库动态抓取并生成报告。
- 抓取 Push 事件时，会把每条 commit 拆成独立动态，并将 commit message 写入报告。
- 支持按时间范围查看报告，例如最近 1 小时、24 小时、7 天或 30 天。
- 提供轻量 Dashboard，用于订阅管理、报告查看和手动生成报告。

## 新增能力

### 订阅管理

- 新增订阅接口：`POST /api/subscriptions`
- 查询订阅接口：`GET /api/subscriptions`
- 删除订阅接口：`DELETE /api/subscriptions/{subscription_id}`
- 订阅字段支持：
  - `repository_url`：仓库地址，必填
  - `access_token`：访问令牌，可选
  - `interval_seconds`：订阅间隔，支持秒级配置
  - `notification_channel`：通知通道，可选

### 仓库抓取

- 支持 GitHub 仓库 Events API。
- 支持 Gitee 仓库 Events API。
- 支持 GitHub/Gitee Push 事件中的多 commit 拆分。
- 每条 commit message 会作为独立仓库动态保存，并进入报告内容。
- 远程请求失败、响应格式异常、令牌解密失败等错误会转换为中文结构化错误。

### 报告生成

- 手动运行订阅接口：`POST /api/subscriptions/{subscription_id}/run`
- 查询报告接口：`GET /api/reports`
- 支持报告时间范围筛选：

```text
GET /api/reports?within_seconds=3600
GET /api/reports?within_seconds=86400
GET /api/reports?within_seconds=604800
```

- 报告内容使用 Markdown 模板生成。
- 重复仓库事件会通过 `external_id` 幂等去重。

### Dashboard

- Dashboard 入口：`GET /`
- 支持创建订阅。
- 支持删除订阅。
- 支持手动生成报告。
- 支持查看报告列表。
- 支持通过下拉框筛选报告时间范围。
- 所有表单字段、交互提示和错误提示使用中文。

### 统一响应结构

所有 JSON API 使用统一响应结构：

```json
{
  "code": 200,
  "data": {},
  "success": true
}
```

错误响应示例：

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

## 技术栈

- Python 3.12
- FastAPI
- Pydantic V2
- SQLAlchemy 2.x Async
- SQLite + aiosqlite
- httpx
- cryptography
- pytest
- Ruff
- uv

## 测试与质量

当前版本覆盖以下测试场景：

- 健康检查接口
- Dashboard 页面渲染
- GitHub/Gitee 订阅创建
- 公开仓库无 token 订阅
- token 加密入库
- 重复订阅冲突
- 删除不存在订阅
- GitHub/Gitee 抓取客户端
- Push 事件 commit message 拆分
- 手动运行订阅并生成报告
- 报告时间范围筛选
- Sentinel Agent 编排流程

验证结果：

```text
pytest: 17 passed
ruff check: All checks passed
```

## 已知限制

- 当前版本尚未接入定时调度，订阅抓取需要通过 Dashboard 或 API 手动触发。
- 通知发送当前使用空实现，尚未接入邮件、Webhook、Slack、企业微信等真实通知通道。
- 抓取逻辑基于平台 Events API，尚未针对 Issue、Pull Request、Release 等资源做专用 API 聚合。
- 当前数据库使用 SQLite，适合本地开发和轻量部署；生产环境可后续迁移到 PostgreSQL。

## 升级与发布建议

- 使用 Git 标签标记版本：

```powershell
git tag -a v0.0.1 -F RELEASE_NOTES.md
```

- 发布前建议执行：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```
