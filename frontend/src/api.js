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

export const fetchHealth    = () => request("/health");
export const fetchReports   = () => request("/reports");
export const fetchMetrics   = () => request("/metrics");
export const fetchTables    = (rapport) => request(`/tables${rapport ? `?rapport=${encodeURIComponent(rapport)}` : ""}`);
export const fetchCompanies = () => request("/companies");
export const fetchPdfs      = () => request("/pdfs");
export const reingest       = () => request("/ingest", { method: "POST" });
export const fetchAnalytics = () => request("/analytics");
export const trackEvent     = (type) =>
  request("/track", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type }),
  }).catch(() => {});

export async function sendChat(message, history, { rapport, company, year, sector } = {}) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, rapport, company, year, sector }),
  });
}

export async function sendChatStream(message, history, { rapport, company, year, sector } = {}, { onToken, onDone, onError } = {}) {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, history, rapport, company, year, sector }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status}`);
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
