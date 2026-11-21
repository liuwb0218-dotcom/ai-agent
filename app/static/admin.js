/* ========== 管理后台逻辑 ========== */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const LS_TOKEN = "ai_agent_token";
  const LS_THEME = "ai_agent_theme";

  let token = localStorage.getItem(LS_TOKEN) || "";
  let page = 1;
  let keyword = "";
  let total = 0;
  const PAGE_SIZE = 20;

  applyTheme(localStorage.getItem(LS_THEME) || "light");
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
  }
  $("#themeBtn").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme;
    const next = cur === "light" ? "dark" : "light";
    applyTheme(next);
    localStorage.setItem(LS_THEME, next);
  });

  async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const resp = await fetch(path, { ...options, headers });
    if (resp.status === 401) { window.location.href = "/"; throw new Error("登录失效"); }
    if (resp.status === 403) { window.location.href = "/"; throw new Error("无权限"); }
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error((typeof data.detail === "string" ? data.detail : "请求失败") || `HTTP ${resp.status}`);
    return data;
  }

  function esc(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  async function loadUsers() {
    const rows = $("#userRows");
    rows.innerHTML = '<tr><td colspan="8" class="admin-empty">加载中…</td></tr>';
    try {
      const data = await apiFetch(`/api/admin/users?page=${page}&page_size=${PAGE_SIZE}&keyword=${encodeURIComponent(keyword)}`);
      total = data.total;
      $("#pageInfo").textContent = `第 ${data.page} 页 / 共 ${Math.max(1, Math.ceil(total / PAGE_SIZE))} 页（${total} 人）`;
      $("#prevBtn").disabled = page <= 1;
      $("#nextBtn").disabled = page >= Math.max(1, Math.ceil(total / PAGE_SIZE));
      if (!data.users.length) {
        rows.innerHTML = '<tr><td colspan="8" class="admin-empty">暂无用户</td></tr>';
        return;
      }
      rows.innerHTML = "";
      for (const u of data.users) {
        const tr = document.createElement("tr");
        const roleOpts = ["admin", "user"].map((r) =>
          `<option value="${r}" ${u.role === r ? "selected" : ""}>${r === "admin" ? "管理员" : "普通用户"}</option>`).join("");
        tr.innerHTML = `
          <td>${u.id}</td>
          <td><b>${esc(u.username)}</b></td>
          <td>${esc(u.nickname)}</td>
          <td>${esc(u.email || "-")}</td>
          <td><select class="role-select" data-id="${u.id}">${roleOpts}</select></td>
          <td><span class="badge ${u.status === 1 ? "ok" : "fail"}">${u.status === 1 ? "正常" : "禁用"}</span></td>
          <td>${esc((u.created_at || "").toString().replace("T", " ").slice(0, 19))}</td>
          <td class="admin-actions">
            <button class="btn btn-small" data-act="toggle" data-id="${u.id}" data-status="${u.status}">${u.status === 1 ? "禁用" : "启用"}</button>
            <button class="btn btn-small" data-act="reset" data-id="${u.id}">重置密码</button>
            <button class="btn btn-small btn-danger" data-act="delete" data-id="${u.id}">删除</button>
          </td>`;
        rows.appendChild(tr);
      }
    } catch (err) {
      rows.innerHTML = `<tr><td colspan="8" class="admin-empty">加载失败：${esc(err.message)}</td></tr>`;
    }
  }

  async function patchUser(id, body) {
    await apiFetch(`/api/admin/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  $("#userRows").addEventListener("change", async (e) => {
    if (!e.target.classList.contains("role-select")) return;
    const id = Number(e.target.dataset.id);
    try {
      await patchUser(id, { role: e.target.value });
    } catch (err) {
      window.alert("修改角色失败：" + err.message);
      loadUsers();
    }
  });

  $("#userRows").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const act = btn.dataset.act;
    try {
      if (act === "toggle") {
        await patchUser(id, { status: btn.dataset.status === "1" ? 0 : 1 });
      } else if (act === "reset") {
        const np = window.prompt("请输入新密码（至少 6 位）：");
        if (!np || np.length < 6) { window.alert("密码至少 6 位"); return; }
        await apiFetch(`/api/admin/users/${id}/reset-password`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ new_password: np }),
        });
        window.alert("密码已重置");
      } else if (act === "delete") {
        if (!window.confirm("确定删除该用户吗？此操作不可恢复！")) return;
        await apiFetch(`/api/admin/users/${id}`, { method: "DELETE" });
      }
      loadUsers();
    } catch (err) {
      window.alert("操作失败：" + err.message);
    }
  });

  $("#searchBtn").addEventListener("click", () => {
    keyword = $("#searchInput").value.trim();
    page = 1;
    loadUsers();
  });
  $("#searchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      keyword = $("#searchInput").value.trim();
      page = 1;
      loadUsers();
    }
  });
  $("#prevBtn").addEventListener("click", () => { if (page > 1) { page--; loadUsers(); } });
  $("#nextBtn").addEventListener("click", () => { if (page < Math.ceil(total / PAGE_SIZE)) { page++; loadUsers(); } });
  $("#backBtn").addEventListener("click", () => { window.location.href = "/"; });
  $("#logoutBtn").addEventListener("click", () => {
    localStorage.removeItem("ai_agent_token");
    localStorage.removeItem("ai_agent_user");
    window.location.href = "/";
  });

  loadUsers();

  // ---- 标签页切换 ----
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $("#panelUsers").hidden = b.dataset.tab !== "users";
      $("#panelOrders").hidden = b.dataset.tab !== "orders";
      $("#panelKnowledge").hidden = b.dataset.tab !== "knowledge";
      if (b.dataset.tab === "orders") loadOrders();
      if (b.dataset.tab === "knowledge") loadKnowledge();
    });
  });

  // ---- 订单管理 ----
  let orderPage = 1;
  let orderKeyword = "";
  let orderStatus = "";
  let orderTotal = 0;
  const ORDER_PAGE_SIZE = 20;

  async function loadOrders() {
    const rows = $("#orderRows");
    rows.innerHTML = '<tr><td colspan="9" class="admin-empty">加载中…</td></tr>';
    try {
      const q = `/api/admin/orders?page=${orderPage}&page_size=${ORDER_PAGE_SIZE}` +
        `&status=${encodeURIComponent(orderStatus)}&keyword=${encodeURIComponent(orderKeyword)}`;
      const data = await apiFetch(q);
      orderTotal = data.total;
      const pages = Math.max(1, Math.ceil(orderTotal / ORDER_PAGE_SIZE));
      $("#orderPageInfo").textContent = `第 ${data.page} 页 / 共 ${pages} 页（${orderTotal} 单）`;
      $("#orderPrevBtn").disabled = orderPage <= 1;
      $("#orderNextBtn").disabled = orderPage >= pages;
      if (!data.orders.length) {
        rows.innerHTML = '<tr><td colspan="9" class="admin-empty">暂无订单</td></tr>';
        return;
      }
      rows.innerHTML = "";
      const statusCls = { "待支付": "st-pending", "已支付": "st-paid", "已发货": "st-shipped", "已完成": "st-done", "已取消": "st-cancel" };
      for (const o of data.orders) {
        const tr = document.createElement("tr");
        const actions = [];
        if (o.status === "待支付" || o.status === "已支付") {
          actions.push(`<button class="btn btn-small" data-act="cancel" data-id="${esc(o.order_id)}">取消</button>`);
        }
        if (o.status === "已支付") {
          actions.push(`<button class="btn btn-small" data-act="ship" data-id="${esc(o.order_id)}">发货</button>`);
        }
        if (o.status === "已发货") {
          actions.push(`<button class="btn btn-small" data-act="complete" data-id="${esc(o.order_id)}">完成</button>`);
        }
        tr.innerHTML = `
          <td>${o.id}</td>
          <td><b>${esc(o.order_id)}</b></td>
          <td>${o.user_id}</td>
          <td>${esc(o.product)}</td>
          <td>${o.quantity}</td>
          <td>¥${esc(o.amount)}</td>
          <td><span class="badge ${statusCls[o.status] || ""}">${esc(o.status)}</span></td>
          <td>${esc((o.created_at || "").toString().replace("T", " ").slice(0, 19))}</td>
          <td class="admin-actions">${actions.join("") || "-"}</td>`;
        rows.appendChild(tr);
      }
    } catch (err) {
      rows.innerHTML = `<tr><td colspan="9" class="admin-empty">加载失败：${esc(err.message)}</td></tr>`;
    }
  }

  $("#orderRows").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;
    if (act === "cancel" && !window.confirm(`确定取消订单 ${id} 吗？库存将回补。`)) return;
    try {
      await apiFetch(`/api/admin/orders/${encodeURIComponent(id)}/${act}`, { method: "PATCH" });
      loadOrders();
    } catch (err) {
      window.alert("操作失败：" + err.message);
    }
  });
  $("#orderSearchBtn").addEventListener("click", () => {
    orderKeyword = $("#orderSearchInput").value.trim();
    orderPage = 1;
    loadOrders();
  });
  $("#orderSearchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      orderKeyword = $("#orderSearchInput").value.trim();
      orderPage = 1;
      loadOrders();
    }
  });
  $("#orderStatusFilter").addEventListener("change", (e) => {
    orderStatus = e.target.value;
    orderPage = 1;
    loadOrders();
  });
  $("#orderPrevBtn").addEventListener("click", () => { if (orderPage > 1) { orderPage--; loadOrders(); } });
  $("#orderNextBtn").addEventListener("click", () => {
    if (orderPage < Math.ceil(orderTotal / ORDER_PAGE_SIZE)) { orderPage++; loadOrders(); }
  });

  // ---- 知识库管理 ----
  async function loadKnowledge() {
    const rows = $("#kbRows");
    rows.innerHTML = '<tr><td colspan="4" class="admin-empty">加载中…</td></tr>';
    try {
      const data = await apiFetch("/api/admin/knowledge/documents");
      if (!data.documents.length) {
        rows.innerHTML = '<tr><td colspan="4" class="admin-empty">知识库为空，上传或导入文档后生效</td></tr>';
        return;
      }
      rows.innerHTML = "";
      for (const d of data.documents) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><b>${esc(d.name)}</b></td>
          <td>${d.chunks}</td>
          <td>${esc(d.created_at)}</td>
          <td class="admin-actions">
            <button class="btn btn-small btn-danger" data-kb-del="${esc(d.doc_id)}" data-kb-name="${esc(d.name)}">删除</button>
          </td>`;
        rows.appendChild(tr);
      }
    } catch (err) {
      rows.innerHTML = `<tr><td colspan="4" class="admin-empty">加载失败：${esc(err.message)}</td></tr>`;
    }
  }

  $("#kbFile").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await apiFetch("/api/admin/knowledge/documents", { method: "POST", body: fd });
      window.alert(`导入成功：${file.name}`);
    } catch (err) {
      window.alert("导入失败：" + err.message);
    }
    e.target.value = "";
    loadKnowledge();
  });

  $("#kbRows").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-kb-del]");
    if (!btn) return;
    if (!window.confirm(`确定删除文档「${btn.dataset.kbName}」吗？`)) return;
    try {
      await apiFetch(`/api/admin/knowledge/documents/${encodeURIComponent(btn.dataset.kbDel)}`, { method: "DELETE" });
      loadKnowledge();
    } catch (err) {
      window.alert("删除失败：" + err.message);
    }
  });
})();
