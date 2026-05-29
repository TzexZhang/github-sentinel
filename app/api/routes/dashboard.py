"""
仪表盘路由，用于展示系统状态和操作界面。
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_home() -> str:
    """返回轻量 Dashboard HTML 页面。"""
    return DASHBOARD_HTML


DASHBOARD_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitHub Sentinel Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #16201c;
      --muted: #66746e;
      --line: #d7ded9;
      --paper: #f6f8f4;
      --panel: #ffffff;
      --accent: #187b58;
      --accent-strong: #0f5e43;
      --shadow: 0 20px 60px rgba(31, 45, 37, 0.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(90deg, rgba(22, 32, 28, 0.035) 1px, transparent 1px),
        linear-gradient(rgba(22, 32, 28, 0.035) 1px, transparent 1px),
        var(--paper);
      background-size: 32px 32px;
      color: var(--ink);
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    }
    button, input, select { font: inherit; }
    .shell { width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 42px; }
    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }
    .brand { display: flex; gap: 16px; align-items: center; }
    .mark {
      width: 54px;
      height: 54px;
      border: 2px solid var(--ink);
      display: grid;
      place-items: center;
      background: #e6f4ed;
      box-shadow: 7px 7px 0 #c0ddcf;
    }
    .mark svg { width: 30px; height: 30px; }
    h1 { margin: 0; font-size: clamp(28px, 4vw, 46px); line-height: 0.95; letter-spacing: 0; }
    .subtitle { margin: 8px 0 0; color: var(--muted); max-width: 680px; }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
    .btn {
      min-height: 40px;
      border: 1px solid var(--ink);
      background: var(--panel);
      color: var(--ink);
      padding: 9px 14px;
      cursor: pointer;
      text-decoration: none;
      box-shadow: 4px 4px 0 #cad5ce;
      transition: transform 120ms ease, box-shadow 120ms ease;
    }
    .btn:hover { transform: translate(-1px, -1px); box-shadow: 6px 6px 0 #cad5ce; }
    .btn.primary { background: var(--accent); color: #fff; border-color: var(--accent-strong); box-shadow: 4px 4px 0 #9dcab7; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 20px; margin-top: 24px; }
    .panel { background: rgba(255,255,255,0.92); border: 1px solid var(--line); box-shadow: var(--shadow); padding: 18px; }
    .panel h2 { margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }
    .metric-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }
    .metric { border: 1px solid var(--line); background: #fbfcfa; padding: 14px; min-height: 94px; }
    .metric span { color: var(--muted); font-size: 13px; }
    .metric strong { display: block; margin-top: 8px; font-size: 30px; line-height: 1; }
    form { display: grid; gap: 10px; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
    input, select { width: 100%; min-height: 40px; border: 1px solid var(--line); background: #fff; color: var(--ink); padding: 8px 10px; }
    .stack { display: grid; gap: 12px; }
    .item { border: 1px solid var(--line); background: #fff; padding: 14px; display: grid; gap: 8px; }
    .item-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .item-actions { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
    .repo { font-weight: 700; overflow-wrap: anywhere; }
    .pill { border: 1px solid var(--line); color: var(--accent-strong); background: #eef7f2; padding: 4px 8px; font-size: 12px; white-space: nowrap; }
    .muted { color: var(--muted); font-size: 13px; }
    .status { margin-top: 12px; color: var(--muted); min-height: 20px; font-size: 13px; }
    .danger { color: #8f1d1d; border-color: #c9aaa5; background: #fff7f6; box-shadow: 4px 4px 0 #e5c6c0; }
    .empty { border: 1px dashed var(--line); color: var(--muted); padding: 18px; background: rgba(255,255,255,0.7); }
    .report-summary { line-height: 1.55; white-space: pre-wrap; }
    .split { display: grid; gap: 20px; }
    @media (max-width: 880px) {
      .topbar, .brand { display: grid; }
      .actions { justify-content: flex-start; }
      .grid { grid-template-columns: 1fr; }
      .metric-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M4 17.5V8.8L12 4l8 4.8v8.7l-8 2.5-8-2.5Z" stroke="#16201c" stroke-width="1.8"/>
            <path d="M8 11.5h8M8 15h5" stroke="#187b58" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <div>
          <h1>GitHub Sentinel Dashboard</h1>
          <p class="subtitle">集中查看订阅仓库、报告输出和服务状态。</p>
        </div>
      </div>
      <div class="actions">
        <button class="btn" type="button" id="refreshButton">刷新</button>
        <a class="btn primary" href="/docs">打开 API 文档</a>
      </div>
    </header>
    <section class="grid">
      <aside class="split">
        <section class="panel">
          <h2>新增订阅</h2>
          <form id="subscriptionForm">
            <label>仓库地址<input id="repositoryUrlInput" name="repository_url" placeholder="例如：https://github.com/encode/httpx" autocomplete="off" required></label>
            <label>访问令牌（可选）<input id="accessTokenInput" name="access_token" type="password" placeholder="公开仓库可不填，私有仓库需填写" autocomplete="off"></label>
            <label>订阅间隔（秒）<input id="intervalInput" name="interval_seconds" type="number" min="1" step="1" value="86400" required></label>
            <label>通知通道<input id="channelInput" name="notification_channel" placeholder="例如：team-webhook" autocomplete="off"></label>
            <button class="btn primary" type="submit">创建订阅</button>
          </form>
          <div class="status" id="formStatus"></div>
        </section>
        <section class="panel">
          <h2>运行状态</h2>
          <div class="stack">
            <div class="item">
              <div class="item-head"><strong>Health</strong><span class="pill" id="healthPill">checking</span></div>
              <span class="muted">接口：/api/health</span>
            </div>
          </div>
        </section>
      </aside>
      <section class="split">
        <section class="metric-row" aria-label="关键指标">
          <div class="metric"><span>订阅数</span><strong id="subscriptionCount">0</strong></div>
          <div class="metric"><span>报告数</span><strong id="reportCount">0</strong></div>
          <div class="metric"><span>活跃订阅</span><strong id="activeCount">0</strong></div>
        </section>
        <section class="panel"><h2>订阅仓库</h2><div class="stack" id="subscriptionsList"><div class="empty">正在加载订阅...</div></div></section>
        <section class="panel">
          <div class="item-head">
            <h2>报告列表</h2>
            <label>报告时间范围
              <select id="reportWindowSelect">
                <option value="">全部报告</option>
                <option value="3600">最近 1 小时</option>
                <option value="86400" selected>最近 24 小时</option>
                <option value="604800">最近 7 天</option>
                <option value="2592000">最近 30 天</option>
              </select>
            </label>
          </div>
          <div class="stack" id="reportsList"><div class="empty">正在加载报告...</div></div>
        </section>
      </section>
    </section>
  </main>
  <script>
    const endpoints = {health: "/api/health", subscriptions: "/api/subscriptions", reports: "/api/reports"};
    const state = {subscriptions: [], reports: []};
    const platformLabel = (value) => ({github: "GitHub", gitee: "Gitee"}[value] || value);
    const intervalLabel = (seconds) => `${seconds} 秒`;
    const formatDate = (value) => value ? new Intl.DateTimeFormat("zh-CN", {dateStyle: "medium", timeStyle: "short"}).format(new Date(value)) : "未知时间";
    const setText = (id, value) => { document.getElementById(id).textContent = value; };
    const reportsEndpoint = () => {
      const seconds = document.getElementById("reportWindowSelect").value;
      return seconds ? `${endpoints.reports}?within_seconds=${seconds}` : endpoints.reports;
    };
    async function requestJson(url, options) {
      const response = await fetch(url, options);
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        throw new Error("服务返回了无法解析的响应。");
      }

      if (!response.ok || payload.success === false) {
        const message = payload.data?.message || "请求处理失败，请稍后重试。";
        throw new Error(message);
      }

      return payload.data;
    }
    function renderSubscriptions() {
      const target = document.getElementById("subscriptionsList");
      if (state.subscriptions.length === 0) {
        target.innerHTML = '<div class="empty">暂无订阅。使用左侧表单添加一个 GitHub 或 Gitee 仓库。</div>';
        return;
      }
      target.innerHTML = state.subscriptions.map((item) => `
        <article class="item">
          <div class="item-head"><div><div class="repo">${platformLabel(item.platform)} · ${item.owner}/${item.repo}</div><div class="muted">创建于 ${formatDate(item.created_at)}</div></div><span class="pill">${intervalLabel(item.interval_seconds)}</span></div>
          <div class="muted">仓库地址：${item.repository_url} · Token：${item.token_configured ? "已加密存储" : "未配置"} · 通知：${item.notification_channel || "未配置"}</div>
          <div class="item-actions">
            <button class="btn primary" type="button" data-run-subscription-id="${item.id}">生成报告</button>
            <button class="btn danger" type="button" data-delete-subscription-id="${item.id}">删除订阅</button>
          </div>
        </article>`).join("");
    }
    function renderReports() {
      const target = document.getElementById("reportsList");
      if (state.reports.length === 0) {
        target.innerHTML = '<div class="empty">暂无报告。点击订阅仓库中的“生成报告”即可立即抓取并生成摘要。</div>';
        return;
      }
      target.innerHTML = state.reports.map((item) => `
        <article class="item">
          <div class="item-head"><div><div class="repo">${item.title}</div><div class="muted">生成于 ${formatDate(item.generated_at)}</div></div><span class="pill">#${item.id}</span></div>
          <div class="report-summary">${item.summary}</div>
        </article>`).join("");
    }
    function renderMetrics() {
      setText("subscriptionCount", state.subscriptions.length);
      setText("reportCount", state.reports.length);
      setText("activeCount", state.subscriptions.filter((item) => item.is_active).length);
    }
    async function loadDashboard() {
      const [health, subscriptions, reports] = await Promise.all([
        requestJson(endpoints.health),
        requestJson(endpoints.subscriptions),
        requestJson(reportsEndpoint()),
      ]);
      state.subscriptions = subscriptions;
      state.reports = reports;
      setText("healthPill", health.status);
      renderMetrics();
      renderSubscriptions();
      renderReports();
    }
    document.getElementById("refreshButton").addEventListener("click", () => {
      loadDashboard().catch((error) => setText("formStatus", error.message));
    });
    document.getElementById("reportWindowSelect").addEventListener("change", () => {
      loadDashboard().catch((error) => setText("formStatus", error.message));
    });
    document.getElementById("subscriptionsList").addEventListener("click", async (event) => {
      const runButton = event.target.closest("[data-run-subscription-id]");
      if (runButton) {
        const subscriptionId = runButton.getAttribute("data-run-subscription-id");
        runButton.disabled = true;
        setText("formStatus", "正在抓取仓库动态并生成报告...");

        try {
          const result = await runSubscription(subscriptionId);
          const message = result.report_id ? "报告已生成。" : "未发现新的仓库动态。";
          setText("formStatus", message);
          await loadDashboard();
        } catch (error) {
          runButton.disabled = false;
          setText("formStatus", error.message);
        }
        return;
      }

      const button = event.target.closest("[data-delete-subscription-id]");
      if (!button) return;

      const subscriptionId = button.getAttribute("data-delete-subscription-id");
      button.disabled = true;
      setText("formStatus", "正在删除订阅...");

      try {
        await deleteSubscription(subscriptionId);
        setText("formStatus", "订阅已删除。");
        await loadDashboard();
      } catch (error) {
        button.disabled = false;
        setText("formStatus", error.message);
      }
    });

    async function deleteSubscription(subscriptionId) {
      await requestJson(`${endpoints.subscriptions}/${subscriptionId}`, {method: "DELETE"});
    }

    async function runSubscription(subscriptionId) {
      return requestJson(`${endpoints.subscriptions}/${subscriptionId}/run`, {method: "POST"});
    }

    document.getElementById("subscriptionForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const payload = {
        repository_url: document.getElementById("repositoryUrlInput").value,
        interval_seconds: Number.parseInt(document.getElementById("intervalInput").value, 10),
        notification_channel: document.getElementById("channelInput").value || null,
      };
      const accessToken = document.getElementById("accessTokenInput").value;
      if (accessToken) {
        payload.access_token = accessToken;
      }
      try {
        await requestJson(endpoints.subscriptions, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        form.reset();
        setText("formStatus", "订阅创建成功。");
        await loadDashboard();
      } catch (error) {
        setText("formStatus", error.message);
      }
    });
    loadDashboard().catch((error) => {
      setText("healthPill", "error");
      setText("formStatus", error.message);
    });
  </script>
</body>
</html>
"""
