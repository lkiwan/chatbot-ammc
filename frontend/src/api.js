const API_BASE = import.meta.env.VITE_API_BASE || "";
const API_TOKEN = import.meta.env.VITE_API_TOKEN || "";

function authHeaders(headers) {
  return API_TOKEN ? { ...headers, "X-Api-Token": API_TOKEN } : headers;
}

async function request(path, options) {
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers: authHeaders(options?.headers),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status}`);
  }
  return res.json();
}

export function pdfUrl(url, page) {
  const q = new URLSearchParams({ url });
  if (API_TOKEN) q.set("token", API_TOKEN);
  const base = `${API_BASE}/api/pdf?${q.toString()}`;
  return page ? `${base}#page=${page}` : base;
}

const SESSION_KEY = "ae-vid";

/**
 * Stable per-tab id, so the backend can count "sessions" (a fresh tab or a new
 * login) separately from visits and from raw request volume.
 */
export function sessionId() {
  try {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = Math.random().toString(36).slice(2, 10);
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return "nosession";
  }
}

function deviceMeta() {
  const meta = { session: sessionId() };
  try {
    if (screen?.width && screen?.height) meta.screen = `${screen.width}x${screen.height}`;
    if (navigator.language) meta.lang = navigator.language;
  } catch {}
  try {
    if (document.referrer && !document.referrer.startsWith(location.origin)) {
      meta.referrer = document.referrer;
    }
  } catch {}
  return meta;
}

export const fetchHealth    = () => request("/health");
export const fetchReports   = () => request("/reports");
export const fetchMetrics   = () => request("/metrics");
export const fetchTables    = (rapport) => request(`/tables${rapport ? `?rapport=${encodeURIComponent(rapport)}` : ""}`);
export const fetchCompanies = () => request("/companies");
export const fetchPdfs      = () => request("/pdfs");
export const reingest       = () => request("/ingest", { method: "POST" });
export const fetchAnalytics = () => request("/analytics");
export const fetchVisitors  = (limit = 200) => request(`/analytics/visitors?limit=${limit}`);
// One request for the whole dashboard — see the note on the endpoint.
export const fetchAnalyticsDeep = (visitors = 300) =>
  request(`/analytics/deep?visitors=${visitors}`);

export function trackEvent(type, role = "", meta = {}) {
  return request("/track", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, role, meta: { ...deviceMeta(), ...meta } }),
  }).catch(() => {});
}

export function trackError(kind, detail = "") {
  return trackEvent("error", "", { kind, error: detail });
}

/** Role of the current session, for analytics attribution. Never used for auth. */
function currentSession() {
  try {
    return JSON.parse(sessionStorage.getItem("ae-session") || "{}");
  } catch {
    return {};
  }
}

function currentRole() {
  return currentSession().role || "";
}

function sessionToken() {
  return currentSession().token || "";
}

function bearerHeaders(extra = {}) {
  const headers = { "Content-Type": "application/json", ...extra };
  const token = sessionToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function sendChat(message, history, { rapport, company, year, sector } = {}) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, rapport, company, year, sector, role: currentRole(), token: sessionToken() }),
  });
}

export async function sendChatStream(message, history, { rapport, company, year, sector } = {}, { onToken, onDone, onError } = {}) {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, history, rapport, company, year, sector, role: currentRole(), token: sessionToken() }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `${res.status}`);
    err.status = res.status;
    throw err;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const evt = JSON.parse(line.slice(6));
        if (evt.done) {
          onDone?.({ sources: evt.sources });
        } else if (evt.token) {
          onToken?.(evt.token);
        }
      } catch {}
    }
  }
}

export const signup = (full_name, email, password) =>
  request("/auth/signup", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ full_name, email, password }) });

export const loginUser = (email, password) =>
  request("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });

export const fetchMe = () => request("/auth/me", { headers: bearerHeaders() });
export const fetchHistory = (limit = 200) => request(`/history?limit=${limit}`, { headers: bearerHeaders() });
export const deleteHistory = () => request("/history", { method: "DELETE", headers: bearerHeaders() });
export const fetchAdminUsers = (limit = 500) => request(`/admin/users?limit=${limit}`);
export const fetchAdminUserHistory = (userId, limit = 100) => request(`/admin/users/${userId}/history?limit=${limit}`);
export const fetchAdminAnon = (limit = 200) => request(`/admin/anon?limit=${limit}`);
export const fetchAdminResetPassword = (userId, password = "") =>
  request(`/admin/users/${userId}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
