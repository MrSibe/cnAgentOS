const app = document.querySelector("#app");

const state = {
  csrfToken: "",
  user: null,
  navigation: [],
  route: window.location.pathname === "/" || window.location.pathname === "/admin" ? "/admin/users" : window.location.pathname,
  tableItems: [],
  lookups: {
    roles: null,
    permissions: null,
    functions: null,
  },
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
    actions: [
      ["edit", "编辑", "secondary"],
      ["status", "启停", "secondary"],
      ["reset", "重置密码", "danger"],
    ],
    form: userForm,
    handleAction: handleUserAction,
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
    actions: [
      ["edit", "编辑", "secondary"],
      ["delete", "删除", "danger"],
    ],
    form: roleForm,
    handleAction: handleRoleAction,
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
    actions: [
      ["edit", "编辑", "secondary"],
      ["status", "启停", "secondary"],
      ["delete", "删除", "danger"],
    ],
    form: functionForm,
    handleAction: handleFunctionAction,
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
  async update(path, data) {
    return this.request(path, { method: "PATCH", body: JSON.stringify(data) });
  },
  async delete(path) {
    return this.request(path, { method: "DELETE" });
  },
};

boot();

function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "dark") {
    document.documentElement.classList.add("dark");
    document.documentElement.classList.remove("light");
  } else if (saved === "light") {
    document.documentElement.classList.add("light");
    document.documentElement.classList.remove("dark");
  }
}

function toggleTheme() {
  const html = document.documentElement;
  if (html.classList.contains("dark")) {
    html.classList.remove("dark");
    html.classList.add("light");
    localStorage.setItem("theme", "light");
  } else {
    html.classList.add("dark");
    html.classList.remove("light");
    localStorage.setItem("theme", "dark");
  }
}

async function boot() {
  initTheme();
  document.body.insertAdjacentHTML("afterbegin", document.querySelector("#icon-sprite").innerHTML);
  try {
    await refreshBootState();
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
          <p class="hint">默认账号仅限本地开发环境。</p>
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
      await refreshBootState();
      history.replaceState({}, "", state.route);
      renderShell();
      await renderPage();
    } catch (err) {
      renderLogin(err.message);
    }
  });
}

function renderShell() {
  const isDark = document.documentElement.classList.contains("dark");
  app.innerHTML = `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand-mark">
          <div class="brand-logo">CN</div>
          <div>
            <div class="brand-title">cnAgentOS</div>
            <div class="brand-subtitle">后台管理系统</div>
          </div>
        </div>
        <nav>${renderNavigation(state.navigation)}</nav>
        <div class="sidebar-footer">
          <button class="theme-toggle" id="theme-toggle" type="button">
            ${icon(isDark ? "sun" : "moon")}
            <span>${isDark ? "亮色模式" : "深色模式"}</span>
          </button>
        </div>
      </aside>
      <section class="main">
        <header class="topbar">
          <div class="user-chip">${escapeHtml(state.user?.display_name || "用户")} · ${escapeHtml(state.user?.username || "")}</div>
          <div class="topbar-actions">
            <button class="btn secondary" id="logout-button" type="button">退出</button>
          </div>
        </header>
        <main class="page" id="page"></main>
      </section>
    </div>
  `;
  document.querySelector("#logout-button").addEventListener("click", logout);
  document.querySelector("#theme-toggle").addEventListener("click", () => {
    toggleTheme();
    renderShell();
    renderPage();
  });
  document.querySelectorAll("[data-route]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.route = button.dataset.route;
      history.pushState({}, "", state.route);
      await renderPage();
      updateActiveNavigation();
    });
  });
}

function renderNavigation(nodes, depth = 0) {
  return nodes
    .map((node) => {
      const children = node.children || [];
      if (children.length) {
        return `<div class="nav-group"><div class="nav-parent">${escapeHtml(node.name)}</div>${renderNavigation(children, depth + 1)}</div>`;
      }
      if (!node.route_path) return "";
      const active = state.route === node.route_path ? "active" : "";
      return `
        <button class="nav-link ${active}" data-route="${escapeHtml(node.route_path)}" type="button" title="${escapeHtml(node.name)}">
        <button class="nav-link ${active}" data-depth="${depth}" data-route="${escapeHtml(node.route_path || "/admin/models")}" type="button" title="${escapeHtml(node.name)}">
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
    state.tableItems = items;
    const formHtml = route.form ? await route.form() : "";
    area.innerHTML = `
      <section class="panel table-wrap">${renderTable(route, items)}</section>
      ${route.form ? `<aside class="panel form-panel">${formHtml}</aside>` : ""}
    `;
    bindCreateForm();
    bindRowActions(route);
  } catch (err) {
    area.innerHTML = `<div class="error">${escapeHtml(err.message)}</div>`;
  }
}

function renderTable(route, items) {
  if (!items.length) return `<div class="empty">暂无数据</div>`;
  const actionHeader = route.actions ? "<th>操作</th>" : "";
  return `
    <table>
      <thead><tr>${route.columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}${actionHeader}</tr></thead>
      <tbody>
        ${items
          .map(
            (item) => `
              <tr data-row="${escapeHtml(JSON.stringify(item).toLowerCase())}">
                ${route.columns
                  .map(([key, , formatter]) => {
                    const value = formatter ? formatter(item[key], item) : escapeHtml(item[key] ?? "-");
                    return `<td>${value}</td>`;
                  })
                  .join("")}
                ${route.actions ? `<td>${renderActionButtons(route.actions, item)}</td>` : ""}
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderActionButtons(actions, item) {
  return `
    <div class="row-actions">
      ${actions
        .map(([key, label, tone]) => `<button class="btn small ${tone || "secondary"}" data-action="${key}" data-id="${escapeHtml(item.id)}" type="button">${escapeHtml(label)}</button>`)
        .join("")}
    </div>
  `;
}

function bindRowActions(route) {
  if (!route.handleAction) return;
  document.querySelectorAll("[data-action][data-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const item = state.tableItems.find((row) => row.id === button.dataset.id);
      if (!item) return;
      try {
        await route.handleAction(button.dataset.action, item);
      } catch (err) {
        showFormError(err.message);
      }
    });
  });
}

function updateActiveNavigation() {
  document.querySelectorAll("[data-route]").forEach((button) => {
    button.classList.toggle("active", button.dataset.route === state.route);
  });
}

async function userForm() {
  const roles = await rolesLookup();
  return `
    <h2>新增用户</h2>
    <form data-create="/api/v1/admin/users" data-array-fields="role_ids">
      <label class="field"><span>登录名</span><input name="username" required /></label>
      <label class="field"><span>展示名称</span><input name="display_name" required /></label>
      <label class="field"><span>初始密码</span><input name="password" type="password" required /></label>
      ${checkboxList("角色", "role_ids", roles, [])}
      <button class="btn" type="submit">创建</button>
    </form>
  `;
}

async function roleForm() {
  const permissions = await permissionsLookup();
  return `
    <h2>新增角色</h2>
    <form data-create="/api/v1/admin/roles" data-array-fields="permission_ids">
      <label class="field"><span>角色代码</span><input name="code" required /></label>
      <label class="field"><span>名称</span><input name="name" required /></label>
      <label class="field"><span>说明</span><textarea name="description"></textarea></label>
      ${checkboxList("权限", "permission_ids", permissions, [])}
      <button class="btn" type="submit">创建</button>
    </form>
  `;
}

async function functionForm() {
  const functions = await functionsLookup();
  const permissions = await permissionsLookup();
  return `
    <h2>新增功能</h2>
    <form data-create="/api/v1/admin/functions">
      <label class="field"><span>功能代码</span><input name="code" required /></label>
      <label class="field"><span>名称</span><input name="name" required /></label>
      <label class="field"><span>父级功能</span><select name="parent_id" data-nullable="true">${options(functions, "", "无父级")}</select></label>
      <label class="field"><span>页面路径</span><input name="route_path" placeholder="/admin/example" data-nullable="true" /></label>
      <label class="field"><span>图标</span><input name="icon" value="circle" data-nullable="true" /></label>
      <label class="field"><span>所需权限</span><select name="required_permission_code" data-nullable="true">${options(permissions, "", "无需权限", "code")}</select></label>
      <label class="field"><span>排序</span><input name="sort_order" type="number" value="100" data-type="number" /></label>
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
      <label class="field"><span>超时秒数</span><input name="timeout_seconds" type="number" value="60" min="1" data-type="number" /></label>
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

async function handleUserAction(action, item) {
  if (action === "edit") {
    const roles = await rolesLookup(true);
    showEditPanel(`
      <h2>编辑用户</h2>
      <form id="edit-form" data-array-fields="role_ids">
        <label class="field"><span>登录名</span><input value="${escapeHtml(item.username)}" disabled /></label>
        <label class="field"><span>展示名称</span><input name="display_name" required value="${escapeHtml(item.display_name)}" /></label>
        ${checkboxList("角色", "role_ids", roles, (item.roles || []).map((role) => role.id))}
        <div class="button-row">
          <button class="btn" type="submit">保存</button>
          <button class="btn secondary" type="button" data-cancel-edit>取消</button>
        </div>
      </form>
    `);
    bindEditSubmit(async (form) => {
      await api.update(`/api/v1/admin/users/${encodeURIComponent(item.id)}`, collectFormData(form));
    });
    return;
  }
  if (action === "status") {
    const nextStatus = item.status === "active" ? "disabled" : "active";
    if (!window.confirm(`确认将用户 ${item.username} 改为 ${nextStatus}？`)) return;
    await api.update(`/api/v1/admin/users/${encodeURIComponent(item.id)}/status`, { status: nextStatus });
    await renderPage();
    return;
  }
  if (action === "reset") {
    const newPassword = window.prompt(`为用户 ${item.username} 设置新密码`);
    if (!newPassword) return;
    await api.create(`/api/v1/admin/users/${encodeURIComponent(item.id)}/password-reset`, { new_password: newPassword });
    showNotice("密码已重置。");
  }
}

async function handleRoleAction(action, item) {
  if (action === "edit") {
    const permissions = await permissionsLookup(true);
    const grantedIds = permissions.filter((permission) => (item.permissions || []).includes(permission.code)).map((permission) => permission.id);
    showEditPanel(`
      <h2>编辑角色</h2>
      <form id="edit-form" data-array-fields="permission_ids">
        <label class="field"><span>角色代码</span><input value="${escapeHtml(item.code)}" disabled /></label>
        <label class="field"><span>名称</span><input name="name" required value="${escapeHtml(item.name)}" /></label>
        <label class="field"><span>说明</span><textarea name="description">${escapeHtml(item.description || "")}</textarea></label>
        <label class="field"><span>状态</span><select name="status">${statusOptions(item.status)}</select></label>
        ${checkboxList("权限", "permission_ids", permissions, grantedIds)}
        <div class="button-row">
          <button class="btn" type="submit">保存</button>
          <button class="btn secondary" type="button" data-cancel-edit>取消</button>
        </div>
      </form>
    `);
    bindEditSubmit(async (form) => {
      await api.update(`/api/v1/admin/roles/${encodeURIComponent(item.id)}`, collectFormData(form));
      await afterAdminMutation("/api/v1/admin/roles");
    });
    return;
  }
  if (action === "delete") {
    if (!window.confirm(`确认删除角色 ${item.code}？`)) return;
    await api.delete(`/api/v1/admin/roles/${encodeURIComponent(item.id)}`);
    await afterAdminMutation("/api/v1/admin/roles");
    await renderPage();
  }
}

async function handleFunctionAction(action, item) {
  if (action === "edit") {
    const functions = (await functionsLookup(true)).filter((functionItem) => functionItem.id !== item.id);
    const permissions = await permissionsLookup(true);
    showEditPanel(`
      <h2>编辑功能</h2>
      <form id="edit-form">
        <label class="field"><span>功能代码</span><input value="${escapeHtml(item.code)}" disabled /></label>
        <label class="field"><span>名称</span><input name="name" required value="${escapeHtml(item.name)}" /></label>
        <label class="field"><span>父级功能</span><select name="parent_id" data-nullable="true">${options(functions, item.parent_id || "", "无父级")}</select></label>
        <label class="field"><span>页面路径</span><input name="route_path" value="${escapeHtml(item.route_path || "")}" data-nullable="true" /></label>
        <label class="field"><span>图标</span><input name="icon" value="${escapeHtml(item.icon || "")}" data-nullable="true" /></label>
        <label class="field"><span>所需权限</span><select name="required_permission_code" data-nullable="true">${options(permissions, item.required_permission_code || "", "无需权限", "code")}</select></label>
        <label class="field"><span>排序</span><input name="sort_order" type="number" value="${escapeHtml(item.sort_order ?? 0)}" data-type="number" /></label>
        <label class="field"><span>状态</span><select name="status">${statusOptions(item.status)}</select></label>
        <div class="button-row">
          <button class="btn" type="submit">保存</button>
          <button class="btn secondary" type="button" data-cancel-edit>取消</button>
        </div>
      </form>
    `);
    bindEditSubmit(async (form) => {
      await api.update(`/api/v1/admin/functions/${encodeURIComponent(item.id)}`, collectFormData(form));
      await afterAdminMutation("/api/v1/admin/functions");
    });
    return;
  }
  if (action === "status") {
    const nextStatus = item.status === "active" ? "disabled" : "active";
    if (!window.confirm(`确认将功能 ${item.code} 改为 ${nextStatus}？`)) return;
    await api.update(`/api/v1/admin/functions/${encodeURIComponent(item.id)}`, { status: nextStatus });
    await afterAdminMutation("/api/v1/admin/functions");
    await renderPage();
    return;
  }
  if (action === "delete") {
    if (!window.confirm(`确认删除功能 ${item.code}？`)) return;
    await api.delete(`/api/v1/admin/functions/${encodeURIComponent(item.id)}`);
    await afterAdminMutation("/api/v1/admin/functions");
    await renderPage();
  }
}

function showEditPanel(html) {
  const panel = document.querySelector(".form-panel");
  if (!panel) return;
  panel.innerHTML = html;
  panel.querySelector("[data-cancel-edit]")?.addEventListener("click", renderPage);
}

function bindEditSubmit(onSubmit) {
  const form = document.querySelector("#edit-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFormMessages(form);
    try {
      await onSubmit(form);
      await renderPage();
    } catch (err) {
      form.insertAdjacentHTML("afterbegin", `<div class="error">${escapeHtml(err.message)}</div>`);
    }
  });
}

async function rolesLookup(force = false) {
  if (!state.lookups.roles || force) {
    const payload = await api.list("/api/v1/admin/roles?page_size=100&status=active");
    state.lookups.roles = payload.data || [];
  }
  return state.lookups.roles;
}

async function permissionsLookup(force = false) {
  if (!state.lookups.permissions || force) {
    const payload = await api.list("/api/v1/admin/permissions");
    state.lookups.permissions = payload.data || [];
  }
  return state.lookups.permissions;
}

async function functionsLookup(force = false) {
  if (!state.lookups.functions || force) {
    const payload = await api.list("/api/v1/admin/functions");
    state.lookups.functions = payload.data || [];
  }
  return state.lookups.functions;
}

function invalidateLookupsForMutation(path) {
  if (path.startsWith("/api/v1/admin/roles")) {
    state.lookups.roles = null;
  }
  if (path.startsWith("/api/v1/admin/functions")) {
    state.lookups.functions = null;
  }
}

async function afterAdminMutation(path) {
  invalidateLookupsForMutation(path);
  if (path.startsWith("/api/v1/admin/roles") || path.startsWith("/api/v1/admin/functions")) {
    await refreshNavigation();
  }
}

async function refreshNavigation() {
  await refreshBootState();
  renderShell();
  updateActiveNavigation();
}

async function refreshBootState() {
  const payload = (await api.request("/api/v1/auth/boot")).data;
  state.user = payload.user;
  state.csrfToken = payload.csrf_token || "";
  state.navigation = payload.navigation;
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
      buffer = buffer.replaceAll("\r\n", "\n");
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      events.forEach((raw) => applySseEvent(raw, output));
    }
  } catch (err) {
    output.textContent = err.message;
  }
}

function applySseEvent(raw, output) {
  const lines = raw.replaceAll("\r\n", "\n").split("\n");
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
      clearFormMessages(form);
      try {
        await api.create(form.dataset.create, collectFormData(form));
        await afterAdminMutation(form.dataset.create);
        await renderPage();
      } catch (err) {
        form.insertAdjacentHTML("afterbegin", `<div class="error">${escapeHtml(err.message)}</div>`);
      }
    });
  });
}

function collectFormData(form) {
  const formData = new FormData(form);
  const arrayFields = (form.dataset.arrayFields || "").split(",").map((item) => item.trim()).filter(Boolean);
  const data = {};
  const namedControls = Array.from(form.querySelectorAll("[name]"));
  const fieldNames = [...new Set(namedControls.map((control) => control.name))];
  fieldNames.forEach((name) => {
    const control = namedControls.find((item) => item.name === name);
    if (arrayFields.includes(name)) {
      data[name] = formData.getAll(name);
      return;
    }
    let value = formData.get(name);
    if (control?.dataset.type === "number") {
      value = value === "" ? 0 : Number(value);
    }
    if (control?.dataset.nullable === "true" && value === "") {
      value = null;
    }
    data[name] = value;
  });
  arrayFields.forEach((name) => {
    if (!Object.prototype.hasOwnProperty.call(data, name)) data[name] = [];
  });
  return data;
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

function checkboxList(label, name, items, selectedIds) {
  const selected = new Set(selectedIds || []);
  const body = items.length
    ? items
        .map(
          (item) => `
            <label class="check-item">
              <input type="checkbox" name="${escapeHtml(name)}" value="${escapeHtml(item.id)}" ${selected.has(item.id) ? "checked" : ""} />
              <span>${escapeHtml(item.name)}<small>${escapeHtml(item.code || "")}</small></span>
            </label>
          `,
        )
        .join("")
    : `<div class="empty compact">暂无可选项</div>`;
  return `
    <fieldset class="check-field">
      <legend>${escapeHtml(label)}</legend>
      <div class="check-list">${body}</div>
    </fieldset>
  `;
}

function options(items, selectedValue = "", emptyLabel = "", valueKey = "id") {
  const selected = String(selectedValue || "");
  const emptyOption = emptyLabel ? `<option value="" ${selected === "" ? "selected" : ""}>${escapeHtml(emptyLabel)}</option>` : "";
  return `${emptyOption}${items
    .map((item) => {
      const value = String(item[valueKey] || "");
      const label = item.code ? `${item.name} (${item.code})` : item.name;
      return `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
    })
    .join("")}`;
}

function statusOptions(value) {
  return `
    <option value="active" ${value === "active" ? "selected" : ""}>active</option>
    <option value="disabled" ${value === "disabled" ? "selected" : ""}>disabled</option>
  `;
}

function showNotice(message) {
  const panel = document.querySelector(".form-panel");
  panel?.insertAdjacentHTML("afterbegin", `<div class="notice">${escapeHtml(message)}</div>`);
}

function showFormError(message) {
  const panel = document.querySelector(".form-panel") || document.querySelector("#content-area");
  panel?.insertAdjacentHTML("afterbegin", `<div class="error">${escapeHtml(message)}</div>`);
}

function clearFormMessages(form) {
  form.querySelectorAll(".error, .notice").forEach((node) => node.remove());
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
  const id = `icon-${name || "circle"}`;
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
