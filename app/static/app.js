/* ========== AI 智能客服 Agent 前端逻辑（含登录/注册/个人资料） ========== */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // ---- 状态 ----
  const LS_TOKEN = "ai_agent_token";
  const LS_USER = "ai_agent_user";
  const LS_SESSION = "ai_agent_session_id";
  const LS_THEME = "ai_agent_theme";

  let token = localStorage.getItem(LS_TOKEN) || "";
  let currentUser = null;
  let authMode = "login"; // login | register
  let sessionId = localStorage.getItem(LS_SESSION) || "";
  let sending = false;

  // ---- DOM ----
  const messagesEl = $("#messages");
  const welcomeEl = $("#welcome");
  const inputEl = $("#input");
  const sendBtn = $("#sendBtn");
  const sessionChip = $("#sessionChip");
  const historyModal = $("#historyModal");
  const historyBody = $("#historyBody");
  const authView = $("#authView");
  const chatView = $("#chatView");
  const userNickname = $("#userNickname");
  const userAvatar = $("#userAvatar");
  const userDropdown = $("#userDropdown");
  const adminBtn = $("#adminBtn");

  // ---- 主题 ----
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(LS_THEME, theme);
  }
  applyTheme(localStorage.getItem(LS_THEME) || "light");
  $("#themeBtn").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme;
    applyTheme(cur === "light" ? "dark" : "light");
  });

  // ---- API 封装 ----
  async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const resp = await fetch(path, { ...options, headers });
    if (resp.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/register") {
      logout(false);
      throw new Error("登录已失效，请重新登录");
    }
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "请求失败";
      throw new Error(detail || `HTTP ${resp.status}`);
    }
    return data;
  }

  function setUser(user) {
    currentUser = user;
    localStorage.setItem(LS_USER, JSON.stringify(user));
    userNickname.textContent = user.nickname || user.username;
    userAvatar.hidden = !user.avatar;
    if (user.avatar) userAvatar.src = user.avatar;
    adminBtn.hidden = user.role !== "admin";
  }

  // ---- 认证视图 ----
  function showAuth() {
    authView.hidden = false;
    chatView.hidden = true;
  }
  function showChat() {
    authView.hidden = true;
    chatView.hidden = false;
  }
  function enterChat() {
    showChat();
    if (sessionId) {
      sessionChip.textContent = `会话: ${sessionId.slice(0, 12)}…`;
      loadChatHistory();
    } else {
      sessionChip.textContent = "会话: 未创建";
    }
  }

  function switchAuthMode(mode) {
    authMode = mode;
    $("#authTitle").textContent = mode === "login" ? "登录" : "注册";
    $("#authSubmit").textContent = mode === "login" ? "登录" : "注册并进入";
    $("#authExtra").hidden = mode !== "register";
    $("#authSwitchLink").textContent = mode === "login" ? "去注册" : "返回登录";
    $("#authError").hidden = true;
    $("#authPassword").autocomplete = mode === "login" ? "current-password" : "new-password";
  }

  async function submitAuth(e) {
    e.preventDefault();
    const username = $("#authUsername").value.trim();
    const password = $("#authPassword").value;
    const errEl = $("#authError");
    try {
      const body = { username, password };
      if (authMode === "register") {
        body.nickname = $("#authNickname").value.trim() || undefined;
        body.email = $("#authEmail").value.trim() || undefined;
      }
      const data = await apiFetch(`/api/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      token = data.access_token;
      localStorage.setItem(LS_TOKEN, token);
      setUser(data.user);
      $("#authUsername").value = "";
      $("#authPassword").value = "";
      errEl.hidden = true;
      enterChat();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
    }
  }
  $("#authForm").addEventListener("submit", submitAuth);
  $("#authSwitchLink").addEventListener("click", (e) => {
    e.preventDefault();
    switchAuthMode(authMode === "login" ? "register" : "login");
  });

  // ---- 退出登录 ----
  function logout(confirm = true) {
    if (confirm && !window.confirm("确定退出登录吗？")) return;
    token = "";
    currentUser = null;
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
    localStorage.removeItem(LS_SESSION);
    sessionId = "";
    messagesEl.innerHTML = "";
    messagesEl.hidden = true;
    welcomeEl.hidden = false;
    showAuth();
  }
  $("#logoutBtn").addEventListener("click", () => logout());

  // ---- 用户区下拉 ----
  $("#userBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    userDropdown.hidden = !userDropdown.hidden;
  });
  document.addEventListener("click", () => { userDropdown.hidden = true; });
  $("#profileBtn").addEventListener("click", () => openProfile());
  $("#adminBtn").addEventListener("click", () => { window.location.href = "/admin.html"; });

  // ---- 我的订单 ----
  const ordersModal = $("#ordersModal");
  const ordersBody = $("#ordersBody");
  const orderFormModal = $("#orderFormModal");

  function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  async function loadOrders() {
    ordersBody.innerHTML = '<div class="hist-item">加载中…</div>';
    let data;
    try {
      data = await apiFetch("/api/orders?page=1&page_size=50");
    } catch (err) {
      ordersBody.innerHTML = `<div class="hist-item">加载订单失败：${esc(err.message)}</div>`;
      return;
    }
    ordersBody.innerHTML = "";
    const list = data.orders || [];
    if (!list.length) {
      ordersBody.innerHTML = '<div class="hist-item">暂无订单，点击下方「🛒 下单」创建第一笔订单</div>';
      return;
    }
    const statusCls = { "待支付": "st-pending", "已支付": "st-paid", "已发货": "st-shipped", "已完成": "st-done", "已取消": "st-cancel" };
    for (const o of list) {
      const item = document.createElement("div");
      item.className = "order-item";
      item.innerHTML = `
        <div class="order-row">
          <span class="order-id">${esc(o.order_id)}</span>
          <span class="order-status ${statusCls[o.status] || ""}">${esc(o.status)}</span>
        </div>
        <div class="order-row sub">${esc(o.product)} × ${esc(o.quantity)} · ¥${esc(o.amount)}</div>
        <div class="order-row time">${esc(formatTime(o.created_at))}${esc(formatTime(o.paid_at) ? " · 支付 " + formatTime(o.paid_at) : "")}</div>
        ${orderActions(o)}`;
      ordersBody.appendChild(item);
    }
  }

  function orderActions(o) {
    const btns = [];
    if (o.status === "待支付") {
      btns.push(`<button class="btn btn-small" data-act="pay" data-id="${esc(o.order_id)}">去支付</button>`);
      btns.push(`<button class="btn btn-small btn-danger" data-act="cancel" data-id="${esc(o.order_id)}">取消</button>`);
    } else if (o.status === "已发货") {
      btns.push(`<button class="btn btn-small" data-act="confirm" data-id="${esc(o.order_id)}">确认收货</button>`);
    }
    return btns.length ? `<div class="order-actions">${btns.join("")}</div>` : "";
  }

  ordersBody.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const act = btn.dataset.act;
    const id = btn.dataset.id;
    if (act === "cancel" && !window.confirm(`确定取消订单 ${id} 吗？库存将回补。`)) return;
    const path = act === "pay" ? "pay" : act === "cancel" ? "cancel" : "confirm";
    try {
      await apiFetch(`/api/orders/${encodeURIComponent(id)}/${path}`, { method: "POST" });
      await loadOrders();
    } catch (err) {
      window.alert(`操作失败：${err.message}`);
    }
  });

  async function openOrders() {
    ordersModal.hidden = false;
    await loadOrders();
  }
  $("#ordersBtn").addEventListener("click", openOrders);
  $("#ordersClose").addEventListener("click", () => { ordersModal.hidden = true; });
  ordersModal.addEventListener("click", (e) => { if (e.target === ordersModal) ordersModal.hidden = true; });

  // ---- 下单表单 ----
  async function openOrderForm() {
    const sel = $("#orderProductSelect");
    sel.innerHTML = "";
    const errEl = $("#orderFormError");
    errEl.hidden = true;
    let data;
    try {
      data = await apiFetch("/api/products?page=1&page_size=100");
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
      orderFormModal.hidden = false;
      return;
    }
    const inStock = (data.products || []).filter((p) => p.stock > 0);
    if (!inStock.length) {
      errEl.textContent = "暂时没有可下单的商品（库存均为 0）";
      errEl.hidden = false;
      orderFormModal.hidden = false;
      return;
    }
    for (const p of inStock) {
      const opt = document.createElement("option");
      opt.value = p.product_id;
      opt.textContent = `${p.name}（${p.product_id}）¥${p.price} / 库存 ${p.stock}`;
      sel.appendChild(opt);
    }
    $("#orderQuantity").value = "1";
    errEl.hidden = true;
    orderFormModal.hidden = false;
  }
  $("#openOrderFormBtn").addEventListener("click", openOrderForm);
  $("#orderFormClose").addEventListener("click", () => { orderFormModal.hidden = true; });
  orderFormModal.addEventListener("click", (e) => { if (e.target === orderFormModal) orderFormModal.hidden = true; });

  $("#orderSubmit").addEventListener("click", async () => {
    const errEl = $("#orderFormError");
    errEl.hidden = true;
    const product_id = $("#orderProductSelect").value;
    const quantity = parseInt($("#orderQuantity").value, 10);
    if (!product_id || !quantity || quantity < 1) {
      errEl.textContent = "请选择商品并填写有效数量";
      errEl.hidden = false;
      return;
    }
    try {
      const order = await apiFetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id, quantity }),
      });
      orderFormModal.hidden = true;
      await loadOrders();
      window.alert(`下单成功！订单号：${order.order_id}，金额：${order.amount} 元`);
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
    }
  });


  // ---- 个人资料弹层 ----
  function showProfileError(msg) {
    const el = $("#profileError");
    el.textContent = msg;
    el.hidden = !msg;
  }
  async function openProfile() {
    userDropdown.hidden = true;
    showProfileError("");
    $("#pwdError").hidden = true;
    $("#pwdOld").value = "";
    $("#pwdNew").value = "";
    try {
      const me = await apiFetch("/api/auth/me");
      $("#profileUsername").value = me.username;
      $("#profileNickname").value = me.nickname || "";
      $("#profileEmail").value = me.email || "";
      const avatar = $("#profileAvatar");
      if (me.avatar) { avatar.src = me.avatar; avatar.hidden = false; }
      else { avatar.hidden = true; }
      $("#profileModal").hidden = false;
    } catch (err) {
      showProfileError(err.message);
    }
  }
  $("#profileClose").addEventListener("click", () => { $("#profileModal").hidden = true; });
  $("#profileModal").addEventListener("click", (e) => { if (e.target === $("#profileModal")) $("#profileModal").hidden = true; });

  $("#avatarFile").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    showProfileError("");
    try {
      const me = await apiFetch("/api/auth/avatar", { method: "POST", body: fd });
      setUser(me);
      const avatar = $("#profileAvatar");
      avatar.src = me.avatar;
      avatar.hidden = false;
    } catch (err) {
      showProfileError(err.message);
    }
    e.target.value = "";
  });

  $("#profileSave").addEventListener("click", async () => {
    showProfileError("");
    try {
      const me = await apiFetch("/api/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: $("#profileNickname").value.trim(),
          email: $("#profileEmail").value.trim() || null,
        }),
      });
      setUser(me);
      showProfileError("保存成功");
    } catch (err) {
      showProfileError(err.message);
    }
  });

  $("#pwdSave").addEventListener("click", async () => {
    const errEl = $("#pwdError");
    errEl.hidden = true;
    try {
      await apiFetch("/api/auth/password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: $("#pwdOld").value, new_password: $("#pwdNew").value }),
      });
      $("#pwdOld").value = "";
      $("#pwdNew").value = "";
      errEl.textContent = "密码已修改";
      errEl.hidden = false;
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
    }
  });

  // ---- 会话 ----
  function setSession(id) {
    sessionId = id;
    localStorage.setItem(LS_SESSION, id);
    sessionChip.textContent = `会话: ${id.slice(0, 12)}…`;
  }
  function newSession() {
    setSession("");
    messagesEl.innerHTML = "";
    messagesEl.hidden = true;
    welcomeEl.hidden = false;
  }
  $("#newBtn").addEventListener("click", newSession);

  // ---- 消息渲染 ----
  function esc(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function appendMessage(role, content) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const avatar = role === "user" ? "我" : "AI";
    wrap.innerHTML = `
      <div class="msg-avatar">${avatar}</div>
      <div class="msg-body">
        <div class="bubble">${esc(content)}</div>
      </div>`;
    messagesEl.appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  function scrollBottom() {
    const main = $(".chat-main");
    main.scrollTop = main.scrollHeight;
  }

  // ---- 发送 ----  // SSE 流式发送
  async function sendStreamChat(message, handlers) {
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!resp.ok || !resp.body) throw new Error("流式接口不可用，已切换普通模式");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      buf += decoder.decode(value || new Uint8Array(), { stream: !done });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = raw.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        let ev;
        try { ev = JSON.parse(line.slice(6)); } catch (e) { continue; }
        if (ev.type === "meta" && handlers.onMeta) handlers.onMeta(ev);
        else if (ev.type === "tool" && handlers.onTool) handlers.onTool(ev);
        else if (ev.type === "token" && handlers.onToken) handlers.onToken(ev);
        else if (ev.type === "done" && handlers.onDone) handlers.onDone(ev);
        else if (ev.type === "error" && handlers.onError) handlers.onError(ev);
      }
      if (done) break;
    }
  }

  function streamBubble(bodyEl) {
    bodyEl.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-body">
        <div class="bubble"></div>
      </div>`;
    return bodyEl.querySelector(".bubble");
  }

  // ---- 发送 ----
  async function send(text) {
    const message = (text ?? inputEl.value).trim();
    if (!message || sending) return;
    inputEl.value = "";
    autosize();

    if (messagesEl.hidden) {
      welcomeEl.hidden = true;
      messagesEl.hidden = false;
    }
    appendMessage("user", message);

    const bodyEl = document.createElement("div");
    bodyEl.className = "msg assistant";
    bodyEl.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-body">
        <div class="bubble"><span class="typing"><span></span><span></span><span></span></span></div>
      </div>`;
    messagesEl.appendChild(bodyEl);
    scrollBottom();

    sending = true;
    sendBtn.disabled = true;
    const bubble = streamBubble(bodyEl);
    const toolLine = (name) => {
      const div = document.createElement("div");
      div.className = "tool-line";
      div.textContent = `🔧 正在${name === "get_order" ? "查询订单" : name === "get_my_orders" ? "查询我的订单" : name === "get_inventory" ? "查询库存" : name === "get_weather" ? "查询天气" : name === "calculator" ? "计算" : "调用工具"}…`;
      bubble.appendChild(div);
    };
    try {
      await sendStreamChat(message, {
        onMeta: (ev) => { if (!sessionId) setSession(ev.session_id); },
        onTool: (ev) => toolLine(ev.tool),
        onToken: (ev) => { bubble.appendChild(document.createTextNode(ev.content)); scrollBottom(); },
        onDone: (ev) => { if (!sessionId) setSession(ev.session_id); },
        onError: (ev) => { throw new Error(ev.message); },
      });
    } catch (err) {
      // 降级：流式失败时回退到同步接口
      try {
        const data = await apiFetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message }),
        });
        if (!sessionId) setSession(data.session_id);
        bubble.textContent = data.reply;
      } catch (err2) {
        bubble.textContent = `⚠️ 请求失败：${err2.message}`;
      }
    } finally {
      sending = false;
      sendBtn.disabled = false;
      inputEl.focus();
      scrollBottom();
    }
  }

  sendBtn.addEventListener("click", () => send());
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  document.querySelectorAll(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => send(chip.dataset.msg));
  });

  function autosize() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
  }
  inputEl.addEventListener("input", autosize);

  // ---- 会话历史 ----
  async function loadChatHistory() {
    if (!sessionId) return;
    try {
      const data = await apiFetch(`/api/conversations/${encodeURIComponent(sessionId)}`);
      const msgs = (data.messages || []).filter((m) => m.role === "user" || m.role === "assistant");
      if (!msgs.length) return;
      welcomeEl.hidden = true;
      messagesEl.hidden = false;
      for (const m of msgs) {
        appendMessage(m.role, m.content || "");
      }
      scrollBottom();
    } catch (err) {
      // 历史加载失败不阻塞使用
    }
  }

  let historyView = "list"; // list | detail，历史弹层当前视图
  let historySession = ""; // 详情视图当前查看的会话 ID

  async function clearSession() {
    const target = historyView === "detail" ? historySession : sessionId;
    if (!target) {
      historyModal.hidden = true;
      newSession();
      return;
    }
    const ok = window.confirm("确定清空该会话吗？此操作会删除该会话的全部历史记录。");
    if (!ok) return;
    try {
      await apiFetch(`/api/conversations/${encodeURIComponent(target)}`, { method: "DELETE" });
    } catch (err) {
      window.alert("清空会话失败：" + err.message);
      return;
    }
    if (historyView === "detail") {
      if (target === sessionId) newSession();
      await showHistoryList();
    } else {
      historyModal.hidden = true;
      newSession();
    }
  }

  // ---- 历史弹层（会话列表 + 详情两级视图） ----
  function formatTime(ts) {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60_000) return "刚刚";
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  async function openHistory() {
    historyModal.hidden = false;
    await showHistoryList();
  }

  async function showHistoryList() {
    historyView = "list";
    historySession = "";
    $("#historyBack").hidden = true;
    $("#clearBtn").hidden = true;
    historyBody.innerHTML = '<div class="hist-item">加载中…</div>';
    try {
      const data = await apiFetch("/api/conversations");
      const sessions = data.sessions || [];
      historyBody.innerHTML = "";
      if (!sessions.length) {
        historyBody.innerHTML = '<div class="hist-item">暂无历史会话</div>';
        return;
      }
      for (const s of sessions) {
        const item = document.createElement("div");
        item.className = "hist-item hist-session";
        item.innerHTML = `<span class="h-content">${esc(s.preview || "(空会话)")}</span><span class="h-meta">${s.message_count} 条 · ${formatTime(s.updated_at)}</span>`;
        item.addEventListener("click", () => showHistoryDetail(s.session_id));
        historyBody.appendChild(item);
      }
    } catch (err) {
      historyBody.innerHTML = '<div class="hist-item">加载历史失败，请重试</div>';
    }
  }

  async function showHistoryDetail(sid) {
    historyView = "detail";
    historySession = sid;
    $("#historyBack").hidden = false;
    $("#clearBtn").hidden = false;
    historyBody.innerHTML = '<div class="hist-item">加载中…</div>';
    try {
      const data = await apiFetch(`/api/conversations/${encodeURIComponent(sid)}`);
      const msgs = (data.messages || []).filter((m) => m.role === "user" || m.role === "assistant");
      historyBody.innerHTML = "";
      if (!msgs.length) {
        historyBody.innerHTML = '<div class="hist-item">暂无历史消息</div>';
        return;
      }
      for (const m of msgs) {
        const item = document.createElement("div");
        item.className = `hist-item ${m.role}`;
        item.innerHTML = `<span class="h-role">${m.role === "user" ? "用户" : "助手"}</span><span class="h-content">${esc(m.content)}</span>`;
        historyBody.appendChild(item);
      }
    } catch (err) {
      historyBody.innerHTML = '<div class="hist-item">加载历史失败，请重试</div>';
    }
  }

  $("#historyBtn").addEventListener("click", openHistory);
  $("#historyBack").addEventListener("click", showHistoryList);
  $("#modalClose").addEventListener("click", () => { historyModal.hidden = true; });
  $("#clearBtn").addEventListener("click", clearSession);
  $("#clearTopBtn").addEventListener("click", clearSession);
  historyModal.addEventListener("click", (e) => { if (e.target === historyModal) historyModal.hidden = true; });

  // ---- 初始化 ----
  async function init() {
    switchAuthMode("login");
    if (!token) {
      showAuth();
      return;
    }
    try {
      const me = await apiFetch("/api/auth/me");
      setUser(me);
      enterChat();
    } catch (err) {
      // token 无效则回登录
      token = "";
      localStorage.removeItem(LS_TOKEN);
      showAuth();
    }
  }
  init();
})();
