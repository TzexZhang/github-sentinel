"""轻量级仪表盘路由。"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_home() -> str:
    """返回轻量级仪表盘页面。"""
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
      background: var(--paper);
      color: var(--ink);
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    }
    button, input { font: inherit; }
    .shell { width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 42px; }
    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: clamp(28px, 4vw, 44px); line-height: 1; letter-spacing: 0; }
    .subtitle { margin: 8px 0 0; color: var(--muted); max-width: 700px; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 20px; margin-top: 24px; }
    .panel { background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow); padding: 18px; }
    .panel h2 { margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }
    .metric-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }
    .metric { border: 1px solid var(--line); background: #fbfcfa; padding: 14px; min-height: 88px; }
    .metric span { color: var(--muted); font-size: 13px; }
    .metric strong { display: block; margin-top: 8px; font-size: 30px; line-height: 1; }
    form, .stack, .split { display: grid; gap: 12px; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
    input { width: 100%; min-height: 40px; border: 1px solid var(--line); background: #fff; color: var(--ink); padding: 8px 10px; }
    .btn {
      min-height: 40px;
      border: 1px solid var(--ink);
      background: var(--panel);
      color: var(--ink);
      padding: 9px 14px;
      cursor: pointer;
      text-decoration: none;
      box-shadow: 4px 4px 0 #cad5ce;
    }
    .btn.primary { background: var(--accent); color: #fff; border-color: var(--accent-strong); box-shadow: 4px 4px 0 #9dcab7; }
    .btn.danger { color: #8f1d1d; border-color: #c9aaa5; background: #fff7f6; box-shadow: 4px 4px 0 #e5c6c0; }
    .item { border: 1px solid var(--line); background: #fff; padding: 14px; display: grid; gap: 8px; }
    .item-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .item-actions { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
    .repo { font-weight: 700; overflow-wrap: anywhere; }
    .pill { border: 1px solid var(--line); color: var(--accent-strong); background: #eef7f2; padding: 4px 8px; font-size: 12px; white-space: nowrap; }
    .muted, .status { color: var(--muted); font-size: 13px; }
    .markdown {
      margin: 0;
      max-height: 320px;
      overflow: auto;
      border: 1px solid var(--line);
      background: #fbfcfa;
      padding: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      line-height: 1.55;
      font-family: "Consolas", "SFMono-Regular", monospace;
      font-size: 13px;
    }
    .date-range { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .section-title-row { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .section-title-row h2 { margin: 0; }
    .section-title-row .date-range { width: min(420px, 100%); }
    .status { min-height: 20px; }
    .empty { border: 1px dashed var(--line); color: var(--muted); padding: 18px; background: rgba(255,255,255,0.7); }
    @media (max-width: 880px) {
      .topbar { display: grid; }
      .grid, .date-range { grid-template-columns: 1fr; }
      .metric-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>GitHub Sentinel Dashboard</h1>
        <p class="subtitle">集中管理订阅仓库，并按订阅间隔或日期范围生成仓库报告。</p>
      </div>
      <div><button class="btn" type="button" id="refreshButton">刷新</button> <a class="btn primary" href="/docs">API 文档</a></div>
    </header>
    <section class="grid">
      <aside class="split">
        <section class="panel">
          <h2>新增订阅</h2>
          <form id="subscriptionForm">
            <label>仓库地址<input id="repositoryUrlInput" name="repository_url" placeholder="https://github.com/encode/httpx" autocomplete="off" required></label>
            <label>访问令牌（可选）<input id="accessTokenInput" name="access_token" type="password" autocomplete="off"></label>
            <label>订阅间隔（秒）<input id="intervalInput" name="interval_seconds" type="number" min="1" step="1" value="86400" required></label>
            <label>通知通道<input id="channelInput" name="notification_channel" autocomplete="off"></label>
            <button class="btn primary" type="submit">创建订阅</button>
          </form>
          <div class="status" id="formStatus"></div>
        </section>
        <section class="panel">
          <h2>运行状态</h2>
          <div class="item"><div class="item-head"><strong>Health</strong><span class="pill" id="healthPill">checking</span></div><span class="muted">/api/health</span></div>
        </section>
      </aside>
      <section class="split">
        <section class="metric-row">
          <div class="metric"><span>订阅数</span><strong id="subscriptionCount">0</strong></div>
          <div class="metric"><span>当前报告数</span><strong id="reportCount">0</strong></div>
          <div class="metric"><span>活跃订阅</span><strong id="activeCount">0</strong></div>
        </section>
        <section class="panel">
          <div class="section-title-row">
            <h2>订阅仓库</h2>
            <div class="date-range">
              <label>开始日期<input id="reportStartDateInput" type="date"></label>
              <label>结束日期<input id="reportEndDateInput" type="date"></label>
            </div>
          </div>
          <div class="stack" id="subscriptionsList"><div class="empty">正在加载订阅...</div></div>
        </section>
        <section class="panel"><h2>报告列表</h2><div class="stack" id="reportsList"><div class="empty">请选择订阅仓库。</div></div></section>
      </section>
    </section>
  </main>
  <script>
    const endpoints = {health: "/api/health", subscriptions: "/api/subscriptions"};
    const state = {subscriptions: [], reports: [], selectedSubscriptionId: null};
    const platformLabel = (value) => ({github: "GitHub", gitee: "Gitee"}[value] || value);
    const formatDate = (value) => {
      if (!value) return "未知时间";
      if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)) return value;
      return new Intl.DateTimeFormat("zh-CN", {dateStyle: "medium", timeStyle: "short"}).format(new Date(value));
    };
    const setText = (id, value) => { document.getElementById(id).textContent = value; };

    function todayIsoDate() {
      return new Date().toISOString().slice(0, 10);
    }

    function defaultStartIsoDate() {
      const date = new Date();
      date.setDate(date.getDate() - 1);
      return date.toISOString().slice(0, 10);
    }

    async function requestJson(url, options) {
      const response = await fetch(url, options);
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.data?.message || "请求失败。");
      }
      return payload.data;
    }

    function selectedSubscription() {
      return state.subscriptions.find((item) => String(item.id) === String(state.selectedSubscriptionId));
    }

    function renderSubscriptions() {
      const target = document.getElementById("subscriptionsList");
      if (state.subscriptions.length === 0) {
        target.innerHTML = '<div class="empty">暂无订阅。</div>';
        return;
      }
      target.innerHTML = state.subscriptions.map((item) => `
        <article class="item">
          <div class="item-head"><div><div class="repo">${platformLabel(item.platform)} · ${item.owner}/${item.repo}</div><div class="muted">创建于 ${formatDate(item.created_at)}</div></div><span class="pill">${item.interval_seconds} 秒</span></div>
          <div class="muted">仓库地址：${item.repository_url} · Token：${item.token_configured ? "已配置" : "未配置"} · 通知：${item.notification_channel || "未配置"}</div>
          <div class="item-actions">
            <button class="btn" type="button" data-select-subscription-id="${item.id}">查看报告</button>
            <button class="btn primary" type="button" data-generate-report-id="${item.id}">生成报告</button>
            <button class="btn danger" type="button" data-delete-subscription-id="${item.id}">删除订阅</button>
          </div>
        </article>`).join("");
    }

    function renderReports() {
      const target = document.getElementById("reportsList");
      const subscription = selectedSubscription();
      if (!subscription) {
        target.innerHTML = '<div class="empty">请选择一个订阅仓库查看报告。</div>';
        return;
      }
      if (state.reports.length === 0) {
        target.innerHTML = `<div class="empty">${subscription.owner}/${subscription.repo} 暂无报告。</div>`;
        return;
      }
      target.innerHTML = state.reports.map((item) => `
        <article class="item">
          <div class="item-head"><div><div class="repo">${item.name}</div><div class="muted">生成于 ${formatDate(item.generated_at)}</div></div><span class="pill">#${item.id}</span></div>
          <pre class="markdown">${escapeHtml(item.content_markdown || "")}</pre>
        </article>`).join("");
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function renderMetrics() {
      setText("subscriptionCount", state.subscriptions.length);
      setText("reportCount", state.reports.length);
      setText("activeCount", state.subscriptions.filter((item) => item.is_active).length);
    }

    async function loadReports() {
      if (!state.selectedSubscriptionId) {
        state.reports = [];
        renderMetrics();
        renderReports();
        return;
      }
      state.reports = await requestJson(`${endpoints.subscriptions}/${state.selectedSubscriptionId}/reports`);
      renderMetrics();
      renderReports();
    }

    async function loadDashboard() {
      const [health, subscriptions] = await Promise.all([
        requestJson(endpoints.health),
        requestJson(endpoints.subscriptions),
      ]);
      state.subscriptions = subscriptions;
      if (!state.selectedSubscriptionId && subscriptions.length > 0) {
        state.selectedSubscriptionId = subscriptions[0].id;
      }
      setText("healthPill", health.status);
      renderSubscriptions();
      await loadReports();
    }

    document.getElementById("refreshButton").addEventListener("click", () => {
      loadDashboard().catch((error) => setText("formStatus", error.message));
    });

    document.getElementById("subscriptionsList").addEventListener("click", async (event) => {
      const selectButton = event.target.closest("[data-select-subscription-id]");
      if (selectButton) {
        state.selectedSubscriptionId = selectButton.getAttribute("data-select-subscription-id");
        await loadReports();
        return;
      }

      const generateButton = event.target.closest("[data-generate-report-id]");
      if (generateButton) {
        const subscriptionId = generateButton.getAttribute("data-generate-report-id");
        const startDate = document.getElementById("reportStartDateInput").value;
        const endDate = document.getElementById("reportEndDateInput").value;
        if (!startDate || !endDate) {
          setText("formStatus", "请选择报告开始日期和结束日期。");
          return;
        }
        generateButton.disabled = true;
        setText("formStatus", "正在抓取最新事件并生成报告...");
        try {
          await requestJson(`${endpoints.subscriptions}/${subscriptionId}/reports`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({start_date: startDate, end_date: endDate}),
          });
          state.selectedSubscriptionId = subscriptionId;
          setText("formStatus", "报告已生成。");
          await loadReports();
        } catch (error) {
          setText("formStatus", error.message);
        } finally {
          generateButton.disabled = false;
        }
        return;
      }

      const deleteButton = event.target.closest("[data-delete-subscription-id]");
      if (!deleteButton) return;
      const subscriptionId = deleteButton.getAttribute("data-delete-subscription-id");
      deleteButton.disabled = true;
      setText("formStatus", "正在删除订阅...");
      try {
        await requestJson(`${endpoints.subscriptions}/${subscriptionId}`, {method: "DELETE"});
        if (String(state.selectedSubscriptionId) === String(subscriptionId)) {
          state.selectedSubscriptionId = null;
        }
        setText("formStatus", "订阅已删除。");
        await loadDashboard();
      } catch (error) {
        setText("formStatus", error.message);
      } finally {
        deleteButton.disabled = false;
      }
    });

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
        const created = await requestJson(endpoints.subscriptions, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        form.reset();
        state.selectedSubscriptionId = created.id;
        setText("formStatus", "订阅创建成功。");
        await loadDashboard();
      } catch (error) {
        setText("formStatus", error.message);
      }
    });

    document.getElementById("reportStartDateInput").value = defaultStartIsoDate();
    document.getElementById("reportEndDateInput").value = todayIsoDate();

    loadDashboard().catch((error) => {
      setText("healthPill", "error");
      setText("formStatus", error.message);
    });
  </script>
</body>
</html>
"""
