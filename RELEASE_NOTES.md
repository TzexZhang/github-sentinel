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
