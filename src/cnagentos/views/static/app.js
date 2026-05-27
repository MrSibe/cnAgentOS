const app = document.querySelector("#app");

const state = {
  csrfToken: "",
  user: null,
  navigation: [],
  route: window.location.pathname === "/" || window.location.pathname === "/admin" ? "/admin/users" : window.location.pathname,
};

const routes = {
  "/admin/users": {
    title: "用户管理",
    kicker: "账户、状态与角色摘要",
    loader: () => api.list("/api/v1/admin/users"),
    columns: [
      ["username", "登录名"],
      ["display_name", "展示名称"],
      ["roles", "角色", (value) => value?.map((item) => item.name).join("、") || "-"],
      ["status", "状态", statusBadge],
      ["is_system_admin", "系统保护", (value) => (value ? badge("是", "warn") : badge("否", "off"))],
      ["updated_at", "更新时间", shortTime],
    ],
    form: userForm,
  },
  "/admin/roles": {
    title: "角色权限",
    kicker: "角色定义与权限代码",
    loader: () => api.list("/api/v1/admin/roles"),
    columns: [
      ["code", "角色代码"],
      ["name", "名称"],
      ["description", "说明"],
      ["permissions", "权限", (value) => chips(value || [])],
      ["status", "状态", statusBadge],
      ["is_system", "系统角色", (value) => (value ? badge("是", "warn") : badge("否", "off"))],
    ],
    form: roleForm,
  },
  "/admin/permissions": {
    title: "权限字典",
    kicker: "服务端定义的权限代码，仅用于授权选择和展示",
    loader: () => api.list("/api/v1/admin/permissions"),
    columns: [
      ["code", "权限代码"],
      ["name", "名称"],
      ["module", "模块"],
      ["description", "说明"],
    ],
  },
  "/admin/functions": {
    title: "功能导航",
    kicker: "后台入口、路由与展示权限",
    loader: () => api.list("/api/v1/admin/functions"),
    columns: [
      ["code", "功能代码"],
      ["name", "名称"],
      ["route_path", "页面路径", (value) => value || "-"],
      ["icon", "图标"],
      ["required_permission_code", "所需权限", (value) => value || "-"],
      ["status", "状态", statusBadge],
      ["sort_order", "排序"],
    ],
    form: functionForm,
  },
  "/admin/models": {
    title: "模型配置",
    kicker: "OpenAI 兼容模型、凭据掩码与测试",
    loader: () => api.list("/api/v1/admin/models"),
    columns: [
      ["name", "名称"],
      ["model_name", "模型"],
      ["base_url", "服务地址"],
      ["credential_mask", "凭据", (value) => value || badge("未配置", "off")],
      ["status", "状态", statusBadge],
      ["is_default", "默认", (value) => (value ? badge("默认", "ok") : badge("否", "off"))],
      ["updated_at", "更新时间", shortTime],
    ],
    form: modelForm,
    extra: modelTestPanel,
  },
  "/admin/model-calls": {
    title: "调用记录",
    kicker: "模型调用用途、状态、耗时与 token",
    loader: () => api.list("/api/v1/admin/model-calls"),
    columns: [
      ["model_name", "模型"],
      ["purpose", "用途"],
      ["streamed", "流式", (value) => (value ? badge("SSE", "ok") : badge("普通", "off"))],
      ["status", "状态", statusBadge],
      ["total_tokens", "Token", (value) => value ?? "-"],
      ["latency_ms", "耗时", (value) => (value ? `${value}ms` : "-")],
      ["started_at", "开始时间", shortTime],
    ],
  },
  "/admin/audit-logs": {
    title: "审计日志",
    kicker: "高风险动作的脱敏操作记录",
    loader: () => api.list("/api/v1/admin/audit-logs"),
    columns: [
      ["actor", "操作者", (value) => value?.display_name || "系统"],
      ["action", "动作"],
      ["target_type", "目标类型"],
      ["target_id", "目标 ID"],
      ["result", "结果", statusBadge],
      ["created_at", "发生时间", shortTime],
    ],
  },
};

const api = {
  async request(path, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    if (state.csrfToken && options.method && options.method !== "GET") {
      headers["X-CSRF-Token"] = state.csrfToken;
    }
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    if (response.status === 204) return null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = payload.error?.message || `请求失败：${response.status}`;
      throw new Error(message);
    }
    return payload;
  },
  async list(path) {
    return this.request(path);
  },
  async create(path, data) {
    return this.request(path, { method: "POST", body: JSON.stringify(data) });
  },
};

boot();

async function boot() {
  document.body.insertAdjacentHTML("afterbegin", document.querySelector("#icon-sprite").innerHTML);
  try {
    const payload = (await api.request("/api/v1/auth/boot")).data;
    state.user = payload.user;
    state.csrfToken = payload.csrf_token || "";
    state.navigation = payload.navigation;
    renderShell();
    await renderPage();
  } catch {
    renderLogin();
  }
}

function renderLogin(error = "") {
  app.innerHTML = `
    <main class="login-screen">
      <section class="login-panel">
        <div class="brand-mark">
          <div class="brand-logo">CN</div>
          <div>
            <div class="brand-title">cnAgentOS</div>
            <div class="brand-subtitle">智能瞭望与智能问数</div>
          </div>
        </div>
        ${error ? `<div class="error">${escapeHtml(error)}</div>` : ""}
        <form id="login-form">
          <label class="field"><span>登录名</span><input name="username" autocomplete="username" required value="admin" /></label>
          <label class="field"><span>密码</span><input name="password" type="password" autocomplete="current-password" required value="admin123" /></label>
          <button class="btn" type="submit">登录</button>
        </form>
      </section>
    </main>
  `;
  document.querySelector("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const payload = await api.request("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(form.entries())),
      });
      state.csrfToken = payload.data.csrf_token;
      const bootPayload = (await api.request("/api/v1/auth/boot")).data;
      state.user = bootPayload.user;
      state.navigation = bootPayload.navigation;
      history.replaceState({}, "", state.route);
      renderShell();
      await renderPage();
    } catch (err) {
      renderLogin(err.message);
    }
  });
}

function renderShell() {
  app.innerHTML = `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand-mark">
          <div class="brand-logo">CN</div>
          <div>
            <div class="brand-title">cnAgentOS</div>
            <div class="brand-subtitle">Phase 1</div>
          </div>
        </div>
        <nav>${renderNavigation(state.navigation)}</nav>
      </aside>
      <section class="main">
        <header class="topbar">
          <div class="user-chip">${escapeHtml(state.user?.display_name || "用户")} · ${escapeHtml(state.user?.username || "")}</div>
          <button class="btn secondary" id="logout-button" type="button">退出</button>
        </header>
        <main class="page" id="page"></main>
      </section>
    </div>
  `;
  document.querySelector("#logout-button").addEventListener("click", logout);
  document.querySelectorAll("[data-route]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.route = button.dataset.route;
      history.pushState({}, "", state.route);
      await renderPage();
      updateActiveNavigation();
    });
  });
}

function renderNavigation(nodes) {
  return nodes
    .map((node) => {
      const children = node.children || [];
      if (children.length) {
        return `<div class="nav-group"><div class="nav-parent">${escapeHtml(node.name)}</div>${renderNavigation(children)}</div>`;
      }
      const active = state.route === node.route_path ? "active" : "";
      return `
        <button class="nav-link ${active}" data-route="${escapeHtml(node.route_path || "/admin/models")}" type="button" title="${escapeHtml(node.name)}">
          ${icon(node.icon)}
          <span>${escapeHtml(node.name)}</span>
        </button>
      `;
    })
    .join("");
}

async function renderPage() {
  const page = document.querySelector("#page");
  if (!routes[state.route]) {
    state.route = "/admin/users";
    history.replaceState({}, "", state.route);
  }
  const route = routes[state.route];
  page.innerHTML = `
    <section class="page-header">
      <div>
        <h1 class="page-title">${escapeHtml(route.title)}</h1>
        <div class="page-kicker">${escapeHtml(route.kicker)}</div>
      </div>
      <div class="toolbar">
        <input class="search" id="search-box" placeholder="搜索" />
        <button class="btn secondary" id="refresh-button" type="button">刷新</button>
      </div>
    </section>
    <section id="content-area" class="${route.form ? "grid-2" : "grid-1"}"></section>
    ${route.extra ? `<section id="extra-area"></section>` : ""}
  `;
  document.querySelector("#refresh-button").addEventListener("click", renderPage);
  document.querySelector("#search-box").addEventListener("input", (event) => filterRows(event.target.value));
  await loadRoute(route);
  if (route.extra) route.extra(document.querySelector("#extra-area"));
}

async function loadRoute(route) {
  const area = document.querySelector("#content-area");
  area.innerHTML = `<div class="panel empty">加载中</div>`;
  try {
    const payload = await route.loader();
    const items = payload.data || [];
    area.innerHTML = `
      <section class="panel table-wrap">${renderTable(route.columns, items)}</section>
      ${route.form ? `<aside class="panel form-panel">${route.form()}</aside>` : ""}
    `;
    bindCreateForm();
  } catch (err) {
    area.innerHTML = `<div class="error">${escapeHtml(err.message)}</div>`;
  }
}

function renderTable(columns, items) {
  if (!items.length) return `<div class="empty">暂无数据</div>`;
  return `
    <table>
      <thead><tr>${columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead>
      <tbody>
        ${items
          .map(
            (item) => `
              <tr data-row="${escapeHtml(JSON.stringify(item).toLowerCase())}">
                ${columns
                  .map(([key, , formatter]) => {
                    const value = formatter ? formatter(item[key], item) : escapeHtml(item[key] ?? "-");
                    return `<td>${value}</td>`;
                  })
                  .join("")}
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function updateActiveNavigation() {
  document.querySelectorAll("[data-route]").forEach((button) => {
    button.classList.toggle("active", button.dataset.route === state.route);
  });
}

function userForm() {
  return `
    <h2>新增用户</h2>
    <form data-create="/api/v1/admin/users">
      <label class="field"><span>登录名</span><input name="username" required /></label>
      <label class="field"><span>展示名称</span><input name="display_name" required /></label>
      <label class="field"><span>初始密码</span><input name="password" type="password" required /></label>
      <button class="btn" type="submit">创建</button>
    </form>
  `;
}

function roleForm() {
  return `
    <h2>新增角色</h2>
    <form data-create="/api/v1/admin/roles">
      <label class="field"><span>角色代码</span><input name="code" required /></label>
      <label class="field"><span>名称</span><input name="name" required /></label>
      <label class="field"><span>说明</span><textarea name="description"></textarea></label>
      <button class="btn" type="submit">创建</button>
    </form>
  `;
}

function functionForm() {
  return `
    <h2>新增功能</h2>
    <form data-create="/api/v1/admin/functions">
      <label class="field"><span>功能代码</span><input name="code" required /></label>
      <label class="field"><span>名称</span><input name="name" required /></label>
      <label class="field"><span>页面路径</span><input name="route_path" placeholder="/admin/example" /></label>
      <label class="field"><span>图标</span><input name="icon" value="circle" /></label>
      <label class="field"><span>所需权限</span><input name="required_permission_code" /></label>
      <label class="field"><span>排序</span><input name="sort_order" type="number" value="100" /></label>
      <button class="btn" type="submit">创建</button>
    </form>
  `;
}

function modelForm() {
  return `
    <h2>新增模型</h2>
    <form data-create="/api/v1/admin/models">
      <label class="field"><span>名称</span><input name="name" required /></label>
      <label class="field"><span>模型名</span><input name="model_name" required /></label>
      <label class="field"><span>Base URL</span><input name="base_url" type="url" required placeholder="https://provider.example/v1" /></label>
      <label class="field"><span>API Key</span><input name="api_key" type="password" autocomplete="new-password" /></label>
      <label class="field"><span>超时秒数</span><input name="timeout_seconds" type="number" value="60" min="1" /></label>
      <label class="field"><span>说明</span><textarea name="description"></textarea></label>
      <button class="btn" type="submit">创建</button>
    </form>
  `;
}

function modelTestPanel(container) {
  container.innerHTML = `
    <section class="panel form-panel">
      <h2>模型测试</h2>
      <div class="button-row">
        <input class="search" id="test-model-id" value="model-main" aria-label="模型 ID" />
        <button class="btn secondary" id="normal-test-button" type="button">普通测试</button>
        <button class="btn" id="stream-test-button" type="button">开始 SSE</button>
      </div>
      <div class="stream-box" id="stream-output"></div>
    </section>
  `;
  document.querySelector("#normal-test-button").addEventListener("click", runNormalTest);
  document.querySelector("#stream-test-button").addEventListener("click", runStreamTest);
}

async function runNormalTest() {
  const output = document.querySelector("#stream-output");
  const modelId = document.querySelector("#test-model-id").value.trim();
  output.textContent = "";
  try {
    const payload = await api.request(`/api/v1/admin/models/${encodeURIComponent(modelId)}/connection-tests`, {
      method: "POST",
      body: JSON.stringify({ message: "请回复连接正常", stream: false }),
    });
    const data = payload.data;
    output.textContent = `${data.reply}\n\n调用记录：${data.call_log_id}\n耗时：${data.latency_ms}ms\nToken：${data.usage?.total_tokens ?? "-"}`;
  } catch (err) {
    output.textContent = err.message;
  }
}

async function runStreamTest() {
  const output = document.querySelector("#stream-output");
  const modelId = document.querySelector("#test-model-id").value.trim();
  output.textContent = "";
  try {
    const response = await fetch(`/api/v1/admin/models/${encodeURIComponent(modelId)}/connection-tests/stream`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
      body: JSON.stringify({ message: "请回复连接正常" }),
    });
    if (!response.ok || !response.body) throw new Error("SSE 请求失败");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      events.forEach((raw) => applySseEvent(raw, output));
    }
  } catch (err) {
    output.textContent = err.message;
  }
}

function applySseEvent(raw, output) {
  const lines = raw.split("\n");
  const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
  const dataLine = lines.find((line) => line.startsWith("data:"))?.slice(5).trim();
  if (!event || !dataLine) return;
  const data = JSON.parse(dataLine);
  if (event === "delta") output.textContent += data.content || "";
  if (event === "completed") output.textContent += `\n\n完成：${data.call_log_id || "ok"}`;
  if (event === "error") output.textContent += `\n\n${data.message || "生成失败"}`;
}

function bindCreateForm() {
  document.querySelectorAll("form[data-create]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      try {
        await api.create(form.dataset.create, data);
        await renderPage();
      } catch (err) {
        form.insertAdjacentHTML("afterbegin", `<div class="error">${escapeHtml(err.message)}</div>`);
      }
    });
  });
}

async function logout() {
  await api.request("/api/v1/auth/logout", { method: "POST" }).catch(() => null);
  state.csrfToken = "";
  state.user = null;
  renderLogin();
}

function filterRows(value) {
  const needle = value.trim().toLowerCase();
  document.querySelectorAll("tbody tr").forEach((row) => {
    row.style.display = row.dataset.row.includes(needle) ? "" : "none";
  });
}

function badge(text, type = "") {
  return `<span class="badge ${type}">${escapeHtml(text)}</span>`;
}

function statusBadge(value) {
  const text = value || "-";
  const type = value === "active" || value === "succeeded" ? "ok" : value === "disabled" ? "off" : value === "failed" ? "warn" : "";
  return badge(text, type);
}

function chips(values) {
  if (!values.length) return "-";
  return values.map((item) => badge(item)).join(" ");
}

function shortTime(value) {
  if (!value) return "-";
  return escapeHtml(value.replace("T", " ").replace("Z", ""));
}

function icon(name = "circle") {
  const id = `icon-${name}`;
  return `<svg aria-hidden="true"><use href="#${escapeHtml(id)}"></use></svg>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

window.addEventListener("popstate", async () => {
  state.route = window.location.pathname;
  await renderPage();
  updateActiveNavigation();
});
