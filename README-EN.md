# Git Sentinel

English | [简体中文](README.md)

Git Sentinel is an open-source utility AI Agent designed for developers and project managers. It regularly retrieves and summarizes the latest updates from subscribed GitHub/Gitee repositories, forming a complete project-tracking workflow around subscription management, update retrieval, notifications, report generation, and multi-model summaries.

By collecting and delivering repository updates in time, Git Sentinel helps teams improve collaboration efficiency and project management visibility. It enables users to track project progress, respond to changes faster, and keep projects observable, traceable, and synchronized.

## Table of Contents

- [1. Project Positioning](#1-project-positioning)
- [2. System Capabilities](#2-system-capabilities)
- [3. Core Workflow](#3-core-workflow)
- [4. Use Cases](#4-use-cases)
- [5. Current Capability Scope](#5-current-capability-scope)
- [6. Quick Start](#6-quick-start)
- [7. License](#7-license)

## 1. Project Positioning

Git Sentinel focuses on repository subscription, update retrieval, notification delivery, and report generation.

It is not just a repository browser. It acts as a repository sentinel for team collaboration: after users subscribe to repositories, the system retrieves updates, organizes information, generates reports, and provides a unified entry point for notification delivery.

### 1.1 Target Users

- Developers who need to track dependency projects, open-source projects, or team repositories.
- Project managers who need visibility into progress, key commits, and recent changes.
- Technical leads who need to understand the change rhythm and collaboration status of multiple repositories.
- Team members who need quick project updates through readable reports.

### 1.2 Problems It Solves

- Repository activity is scattered and costly to inspect manually.
- Multi-repository project progress is hard to summarize in time.
- Commits, issues, pull requests, and releases lack unified summaries.
- Team response to project changes often depends on manual reminders.
- Daily, weekly, and project progress reports take time to prepare.

## 2. System Capabilities

### 2.1 Subscription Management

Subscription management centralizes repositories users care about and brings scattered projects into a unified tracking scope.

Capabilities include:

- Add repositories by repository URL.
- View subscribed repositories in one place.
- Support both public and private repository subscription scenarios.
- Configure access credentials for private repositories.
- Manage subscription status by repository.
- Remove repositories that are no longer tracked.
- Hide sensitive credentials and only show whether credentials are configured.

### 2.2 Update Retrieval

Update retrieval continuously collects the latest activity from subscribed repositories so teams can stay aware of project changes.

Capabilities include:

- Retrieve the latest activity from subscribed repositories.
- Summarize Push, Issue, Pull Request, and other project updates.
- Recognize multiple commits in a single push.
- Extract the message of each commit.
- Reduce duplicate activity noise in reports.
- Support update retrieval for both public and private repositories.
- Provide a unified data source for report generation and notifications.

### 2.3 Notification System

The notification system delivers the latest project progress to subscribers.

Capabilities include:

- Configure notification targets for subscriptions.
- Share project progress with subscribers after reports are generated.
- Organize notification content around repository updates, commits, and project reports.
- Support notification forms such as email, webhook, and team collaboration tools.
- Help team members receive key updates without repeatedly checking repositories manually.

### 2.4 Report Generation

Report generation turns repository updates into project progress materials that are easier for teams to read and share.

Capabilities include:

- Generate project progress reports from repository activity.
- Present key commit messages in reports.
- View historical reports bound to a selected subscription.
- Filter report lists by recent time windows or custom date ranges.
- Generate a report from a user-selected date range after refreshing repository events for that period.
- Save report content as Markdown and name reports by repository and date range.
- Record the start date and end date represented by each report.
- Update the existing report when the same subscription and date range are generated again, reducing duplicate report buildup.
- Use the built-in LLM capability to summarize Push, Issue, and Pull Request events. The default provider is the free Zhipu series, with Gemini free-series configuration also available.
- Support report scenarios such as daily reports, weekly reports, release summaries, and project progress summaries.
- Support output forms such as Markdown, HTML, and email body content.

### 2.5 Multi-Model Support

Multi-model support improves report readability and information organization quality, making project reports closer to natural-language summaries.

Capabilities include:

- Provide built-in model capability for natural-language project reports.
- Allow users to configure their own model integration.
- Support integration with mainstream model services.
- Support configuration of model endpoint, model name, access key, and request parameters.
- Allow different model choices for different report scenarios.
- Turn commits, issues, pull requests, and other content into natural-language summaries.

### 2.6 Scheduled Tasks

Scheduled tasks allow repository updates to run automatically at user-defined frequencies, reducing manual triggering effort.

Capabilities include:

- Support second-level task frequency configuration.
- Support common cycles such as daily and weekly execution.
- Support long-running task mode.
- Allow different repositories to use different update frequencies.
- Automatically retrieve updates and generate subsequent reports.
- Record task execution status for troubleshooting.

### 2.7 Graphical Interface

The graphical interface is built with Gradio to lower the usage barrier so non-backend users can complete subscription, retrieval, and report operations.

Capabilities include:

- Provide a Gradio-based visual operation entry.
- Manage and delete subscriptions through forms.
- Automatically load the report list after a subscription is selected.
- Query reports by recent time range or custom date range.
- Separate report-query dates from report-generation dates so users can generate reports for specific periods.
- View report names, generation times, and Markdown content.
- Localize the date picker with Chinese month, weekday, and action labels.
- Reduce reliance on command-line and direct API usage.
- Fit lightweight project management workflows.

### 2.8 Containerized Deployment

Containerization reduces deployment cost and improves runtime consistency across environments.

Capabilities include:

- Deploy the service through containers.
- Start quickly in different server environments.
- Manage runtime configuration through environment variables.
- Standardize application, configuration, and runtime environment.
- Reduce migration, deployment, and delivery costs.

### 2.9 Continuous Integration

Continuous integration improves project stability and delivery quality.

Capabilities include:

- Cover core flows with automated tests.
- Use code checks to maintain baseline quality.
- Run quality validation before releases.
- Build regression verification around subscription, retrieval, report, and notification flows.
- Provide a quality foundation for stable delivery and team collaboration.

### 2.10 Security And Data Protection

Security and data protection reduce the risk of exposing sensitive information and make repository credentials safer.

Capabilities include:

- Access credentials can be configured only when needed.
- Public repositories do not require access credentials.
- Private repository credentials are encrypted before storage.
- Pages and APIs do not display plaintext credentials.
- Error messages avoid exposing sensitive internal details.
- Sensitive configuration is injected through the runtime environment.

## 3. Core Workflow

```text
Create subscription
  -> Configure repository URL and access token
  -> Retrieve latest repository updates manually or on schedule
  -> Organize repository update content
  -> Filter duplicate activity
  -> Generate project progress report
  -> Notify subscribers or enter report viewing flow
```

This workflow turns scattered repository activity into readable reports, supporting team synchronization and project management.

## 4. Use Cases

### 4.1 Open-Source Project Tracking

Developers can subscribe to GitHub open-source repositories and review recent commits and project activity in one place.

### 4.2 Team Project Management

Project managers can use reports to understand recent repository updates without checking each repository manually.

### 4.3 Private Repository Monitoring

Teams can configure access tokens for private repositories and generate internal project progress summaries.

### 4.4 Daily And Weekly Reports

Teams can filter reports by time range and use them for daily reports, weekly reports, or project status updates.

## 5. Current Capability Scope

| Module | Capability |
| ---- | ---- |
| Subscription Management | Add tracked repositories, view subscriptions, remove repositories |
| Update Retrieval | Retrieve repository activity, organize commit messages, reduce duplicate activity |
| Notification System | Configure notification targets and share project progress after report generation |
| Report Generation | Generate Chinese project reports, view historical reports, filter by time range, record report periods, update duplicate period reports |
| Multi-Model Support | Built-in model capability, custom model integration, mainstream model configuration |
| Scheduled Tasks | Second-level frequency, daily/weekly cycles, long-running tasks |
| Graphical Interface | Gradio visual entry with subscription deletion, automatic report-list loading, date-range selection, and report preview |
| Containerization | Standardized deployment and lower cross-environment runtime cost |
| Continuous Integration | Automated tests, quality checks, pre-release validation |
| Security | Optional credentials, encrypted credential storage, no credential exposure in pages or APIs |
| API Contract | Unified response structure and Chinese error messages |

## 6. Quick Start

### 6.1 Install Dependencies

This project uses `uv` to manage Python versions, virtual environments, and dependencies.

```powershell
uv sync --group dev
```

### 6.2 Database File

The default SQLite database path is `./data/github_sentinel.db`. On first startup, the application automatically creates the database file and any missing tables.

For Docker deployments, `docker-compose.yml` mounts host `./data` to container `/app/data` to persist the database file. Do not manually create an empty database file; if production already has an old database file, migrate it before switching `DATABASE_URL`.

> ℹ️ **About the `-shm` / `-wal` auxiliary files**
>
> After starting the service, two companion files appear in `data/` alongside the main `github_sentinel.db`. These are normal artifacts of SQLite **WAL (Write-Ahead Logging) mode**, not redundant or junk files:
>
> | File | Purpose |
> |------|---------|
> | `github_sentinel.db` | Main database, stores all production data (**do not delete**) |
> | `github_sentinel.db-wal` | Write-ahead log. Writes land here first, then are asynchronously merged back into the main DB, improving concurrency |
> | `github_sentinel.db-shm` | Shared-memory index. Coordinates concurrent read/write access to the WAL across connections |
>
> WAL mode is enabled in the project (`PRAGMA journal_mode=WAL` in `app/db/session.py`) to avoid the `database is locked` write conflicts of SQLite's default mode. These three files form one set and **all are required at runtime**.
>
> **Note**: If you must remove `-shm` / `-wal`, **stop the service first** so SQLite can complete a checkpoint (merging WAL data back into the main DB); otherwise unwritten changes may be lost. The files will be regenerated automatically on the next startup because WAL mode stays on. For normal use, just leave them — they are ignored by `.gitignore` and do not affect version control.

### 6.3 Start The Service

```powershell
uv run python -m uvicorn app.main:create_app --factory --reload --timeout-graceful-shutdown 1 --timeout-keep-alive 1
```

After startup, open:

| Page/API | URL |
| ---- | ---- |
| Service Home | `http://127.0.0.1:8000/` |
| API Docs | `http://127.0.0.1:8000/docs` |
| Health Check | `http://127.0.0.1:8000/api/health` |

During local development, the Dashboard keeps Gradio frontend connections open. On Windows, when `--reload` stops at `Waiting for connections to close` after code changes, use the `--timeout-graceful-shutdown 1` flag shown above so stale connections are released quickly during reload.

On Windows, if `uv run uvicorn app.main:create_app --factory --reload` fails with `Failed to canonicalize script path`, use the `uv run python -m uvicorn ...` command above.

### 6.4 Configuration

The project reads non-sensitive defaults from `config/settings.toml`.

Sensitive values should be injected through environment variables and should not be written to config files or committed to the repository.

| Configuration | Purpose |
| ---- | ---- |
| `DATABASE_URL` | Database connection URL |
| `TOKEN_ENCRYPTION_KEY` | Access token encryption key |
| `GITHUB_SENTINEL_CONFIG` | Custom config file path |

Production environments should explicitly set `TOKEN_ENCRYPTION_KEY`. Generate a Fernet key with:

```powershell
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 7. License

This project is open-source under the MIT License. See [LICENSE](LICENSE).
