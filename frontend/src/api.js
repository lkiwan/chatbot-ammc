async function request(path, options) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status}`);
  }
  return res.json();
}

export const fetchHealth = () => request("/health");
export const fetchReport = () => request("/report");
export const fetchMetrics = () => request("/metrics");
export const fetchTables = () => request("/tables");

export async function sendChat(message, history) {
  const data = await request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history })
  });
  return data;
}