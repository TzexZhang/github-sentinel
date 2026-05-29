# GitHub Sentinel v0.0.1

GitHub Sentinel 是一款面向开发者和项目管理人员的开源工具类 AI Agent，用于订阅 GitHub/Gitee 仓库、抓取仓库动态、整理提交记录，并生成项目进展报告。

## 功能特性

- 支持通过仓库地址订阅 GitHub/Gitee 仓库。
- 支持公开仓库不填写 `access_token`，私有仓库可填写访问令牌。
- `access_token` 写入 SQLite 前使用 Fernet 加密，接口不会返回明文或密文。
- 支持手动触发仓库动态抓取并生成报告。
- 抓取 Push 事件时，会把每条 commit 拆成独立动态，并将 commit message 写入报告。
- 支持按时间范围查看报告，例如最近 1 小时、24 小时、7 天或 30 天。
- 提供轻量 Dashboard，用于订阅管理、报告查看和手动生成报告。
