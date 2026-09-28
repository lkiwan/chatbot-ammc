import React, { useEffect, useState, useCallback, useMemo } from "react";
import { fetchAnalyticsDeep, trackError } from "../api.js";

const REFRESH_MS = 30_000;

function flagOf(code) {
  if (!code || code.length !== 2) return "";
  return String.fromCodePoint(
    ...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)
  );
}

function formatWhen(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
}

function timeOnly(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleTimeString();
}

function formatMs(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function duration(firstSeen, lastSeen) {
  if (!firstSeen || !lastSeen) return "—";
  const ms = new Date(lastSeen) - new Date(firstSeen);
  if (Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  if (ms < 86_400_000) return `${(ms / 3_600_000).toFixed(1)}h`;
  return `${Math.round(ms / 86_400_000)}j`;
}

/**
 * Normalises a "top X" list to [name, count] pairs.
 * The API returns pairs, but tolerating {name, count} objects as well means a
 * backend/frontend version mismatch degrades to an empty row instead of
 * throwing "object is not iterable" and blanking the whole dashboard.
 */
function toPairs(rows) {
  return (Array.isArray(rows) ? rows : []).map((r) =>
    Array.isArray(r) ? r : [r?.name ?? "—", r?.count ?? 0]
  );
}

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "logins",   label: "Logins" },
  { key: "chat",     label: "Chat" },
  { key: "visitors", label: "Visitors" },
];

export default function AdminDashboard({ onClose }) {
  const [data, setData]           = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [tab, setTab]             = useState("overview");

  const load = useCallback(() => {
    fetchAnalyticsDeep(300)
      .then((d) => {
        setData(d);
        setError(null);
        setLastUpdated(new Date());
      })
      .catch((e) => {
        setError("Failed to load analytics.");
        trackError("analytics_dashboard_failed", e?.message || "");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => clearInterval(interval);
  }, [load]);

  // Esc closes, so the dashboard can be dismissed without reaching for the mouse.
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="adash-overlay">
      <div className="adash-container">
        <div className="adash-header">
          <div className="adash-header-left">
            <span className="adash-header-icon">
              <svg viewBox="0 0 20 20" fill="none" width="18" height="18">
                <rect x="2" y="11" width="4" height="7" rx="1" fill="currentColor" opacity=".6"/>
                <rect x="8" y="6" width="4" height="12" rx="1" fill="currentColor" opacity=".8"/>
                <rect x="14" y="2" width="4" height="16" rx="1" fill="currentColor"/>
              </svg>
            </span>
            <h2 className="adash-title">Analytics Dashboard</h2>
            <span className="adash-badge">Admin</span>
          </div>
          <div className="adash-header-right">
            {lastUpdated && (
              <span className="adash-updated">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button className="adash-refresh" onClick={load} title="Refresh">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M13.5 2.5A6.5 6.5 0 0 0 2 8M2.5 13.5A6.5 6.5 0 0 0 14 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                <path d="M13.5 2.5v3h-3M2.5 13.5v-3h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <button className="adash-close" onClick={onClose} title="Close dashboard (Esc)">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="adash-tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`adash-tab ${tab === t.key ? "active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="adash-body">
          {loading && <LoadingSkeleton />}
          {error && !loading && <ErrorState message={error} onRetry={load} />}
          {data && !loading && (
            <>
              {tab === "overview" && <OverviewTab data={data} />}
              {tab === "logins"   && <LoginsTab data={data} />}
              {tab === "chat"     && <ChatTab data={data} />}
              {tab === "visitors" && <VisitorsTab visitors={data.visitors || []} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Overview ─────────────────────────────────────────────────────────────── */

function OverviewTab({ data }) {
  const { summary, logins, chat, usage, clients } = data;
  const totalDevices = Object.values(summary.device_breakdown || {}).reduce((s, v) => s + v, 0);
  const totalEvents =
    summary.total_visits + logins.total_attempts + chat.total_questions + usage.errors;

  return (
    <>
      {/* Headline KPIs */}
      <div className="adash-kpi-grid">
        <KpiCard icon={<EyeIcon />}   label="Total Visits"    value={summary.total_visits}  sub="page loads" color="blue" />
        <KpiCard icon={<UsersIcon />} label="Unique Visitors" value={summary.unique_visitors_all ?? 0} sub="all time, by IP" color="purple" />
        <KpiCard icon={<GlobeIcon />} label="Known Locations" value={summary.located_visitors ?? 0} sub={`${summary.unique_visitors_30d ?? 0} unique, 30d`} color="blue" />
        <KpiCard icon={<UserIcon />}  label="Login Attempts"  value={logins.total_attempts}  sub={`${logins.total_failed} failed`} color="teal" />
        <KpiCard icon={<ChatIcon />}  label="Questions"       value={chat.total_questions}  sub={`${chat.unique_askers ?? 0} askers`} color="amber" />
        <KpiCard icon={<DocIcon />}   label="PDFs Opened"     value={usage.pdf_opens}      sub="citations followed" color="purple" />
        <KpiCard icon={<BuildingIcon />} label="Companies Viewed" value={usage.company_selects} sub="sidebar selections" color="teal" />
        <KpiCard icon={<ErrorIcon />} label="Errors"          value={usage.errors}         sub={`${summary.total_demo_exhausted ?? 0} demo limit hits`} color="rose" />
      </div>

      {/* Headline numbers that don't fit the card grid */}
      <div className="adash-charts-row">
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Visits — Last 7 Days</span>
            <span className="adash-card-sub">{totalEvents} total events</span>
          </div>
          <BarChart data={summary.visits_per_day} color="var(--adash-blue)" />
        </div>
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Questions — Last 7 Days</span>
            <span className="adash-card-sub">
              avg {formatMs(chat.avg_latency_ms)} · p95 {formatMs(chat.p95_latency_ms)}
            </span>
          </div>
          <BarChart data={chat.questions_per_day} color="var(--adash-amber)" />
        </div>
      </div>

      <TimelineCard timeline={data.timeline || []} />

      <div className="adash-charts-row">
        <div className="adash-card">
          <div className="adash-card-header">
            <span className="adash-card-title">Device Breakdown</span>
            <span className="adash-card-sub">{totalDevices} total visits</span>
          </div>
          <div className="adash-devices">
            {[
              { key: "desktop", label: "Desktop", icon: <DesktopIcon />, color: "var(--adash-blue)" },
              { key: "mobile",  label: "Mobile",  icon: <MobileIcon />,  color: "var(--adash-teal)" },
              { key: "tablet",  label: "Tablet",  icon: <TabletIcon />,  color: "var(--adash-purple)" },
            ].map(({ key, label, icon, color }) => {
              const count = summary.device_breakdown?.[key] ?? 0;
              const pct = totalDevices > 0 ? Math.round((count / totalDevices) * 100) : 0;
              return (
                <div key={key} className="adash-device-row">
                  <div className="adash-device-label">
                    <span className="adash-device-icon">{icon}</span>
                    <span>{label}</span>
                  </div>
                  <div className="adash-device-bar-wrap">
                    <div className="adash-device-bar-fill" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <div className="adash-device-stats">
                    <span className="adash-device-count">{count}</span>
                    <span className="adash-device-pct">{pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <DistributionCard title="Browsers" rows={clients.browsers} />
        <DistributionCard title="Operating Systems" rows={clients.systems} />
      </div>

      <LocationsCard countries={summary.top_countries} cities={summary.top_cities} />

      <HourHeatmap hours={data.hours} />

      {(summary.total_demo_exhausted ?? 0) > 0 && (
        <AbuseInsight
          exhausted={summary.total_demo_exhausted ?? 0}
          logins={summary.total_demo_logins}
        />
      )}

      <TopListsCard usage={usage} />
    </>
  );
}

function DistributionCard({ title, rows = [] }) {
  const total = rows.reduce((s, r) => s + r.count, 0);
  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">{title}</span>
        <span className="adash-card-sub">{total} events</span>
      </div>
      <div className="adash-devices">
        {rows.length === 0 && <div className="adash-empty">No data</div>}
        {rows.map((r) => {
          const pct = total > 0 ? Math.round((r.count / total) * 100) : 0;
          return (
            <div key={r.name} className="adash-device-row adash-geo-row">
              <div className="adash-device-label">
                <span>{r.name}</span>
              </div>
              <div className="adash-device-stats">
                <span className="adash-device-count">{r.count}</span>
                <span className="adash-device-pct">{pct}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Timeline ─────────────────────────────────────────────────────────────── */

const TL_SERIES = [
  { key: "visits",    label: "Visits",    color: "var(--adash-blue)" },
  { key: "questions", label: "Questions", color: "var(--adash-amber)" },
  { key: "logins",    label: "Logins",    color: "var(--adash-teal)" },
  { key: "pdf_opens", label: "PDF opens", color: "var(--adash-purple)" },
];

function TimelineCard({ timeline }) {
  const [metric, setMetric] = useState("visits");
  const active = TL_SERIES.find((s) => s.key === metric);
  const max = Math.max(...timeline.map((d) => d[metric] || 0), 1);

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Activity — Last 30 Days</span>
        <div className="adash-seg">
          {TL_SERIES.map((s) => (
            <button
              key={s.key}
              className={`adash-seg-btn ${metric === s.key ? "active" : ""}`}
              onClick={() => setMetric(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div className="adash-spark">
        {timeline.map((d) => {
          const v = d[metric] || 0;
          return (
            <div key={d.date} className="adash-spark-col" title={`${d.date} — ${v} ${active.label.toLowerCase()}`}>
              <div className="adash-spark-track">
                <div
                  className="adash-spark-fill"
                  style={{ height: `${(v / max) * 100}%`, background: active.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="adash-spark-axis">
        <span>{timeline[0]?.date}</span>
        <span>{timeline[timeline.length - 1]?.date}</span>
      </div>
    </div>
  );
}

/* ── Hour heatmap ─────────────────────────────────────────────────────────── */

const HOUR_SERIES = [
  { key: "visits",        label: "Visits",        color: "var(--adash-blue)" },
  { key: "questions",     label: "Questions",     color: "var(--adash-amber)" },
  { key: "failed_logins", label: "Failed logins", color: "var(--adash-rose)" },
];

function HourHeatmap({ hours }) {
  if (!hours) return null;
  const [metric, setMetric] = useState("visits");
  const values = hours[metric] || [];
  const max = Math.max(...values, 1);

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Activity by Hour (UTC)</span>
        <div className="adash-seg">
          {HOUR_SERIES.map((s) => (
            <button
              key={s.key}
              className={`adash-seg-btn ${metric === s.key ? "active" : ""}`}
              onClick={() => setMetric(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div className="adash-heat">
        {values.map((v, h) => (
          <div
            key={h}
            className="adash-heat-cell"
            title={`${String(h).padStart(2, "0")}:00 UTC — ${v}`}
            style={{
              background: v === 0 ? "rgba(255,255,255,.03)" : undefined,
              opacity: v === 0 ? 1 : 0.18 + (v / max) * 0.82,
            }}
          >
            <span className="adash-heat-h">{h}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Locations ────────────────────────────────────────────────────────────── */

function LocationsCard({ countries = [], cities = [] }) {
  const total = countries.reduce((s, c) => s + c.visitors, 0);

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Locations</span>
        <span className="adash-card-sub">
          {total} {total === 1 ? "visitor" : "visitors"} resolved
        </span>
      </div>
      {total === 0 && cities.length === 0 ? (
        <div className="adash-empty">No location data yet</div>
      ) : (
        <div className="adash-geo-grid">
          <div>
            <div className="adash-geo-heading">By country</div>
            <div className="adash-devices">
              {countries.length === 0 && <div className="adash-empty">Unknown</div>}
              {countries.map((c) => {
                const pct = total > 0 ? Math.round((c.visitors / total) * 100) : 0;
                return (
                  <div key={c.country_code || c.country} className="adash-device-row">
                    <div className="adash-device-label">
                      <span className="adash-flag">{flagOf(c.country_code)}</span>
                      <span>{c.country}</span>
                    </div>
                    <div className="adash-device-bar-wrap">
                      <div
                        className="adash-device-bar-fill"
                        style={{ width: `${pct}%`, background: "var(--adash-blue)" }}
                      />
                    </div>
                    <div className="adash-device-stats">
                      {c.demo_visitors > 0 && (
                        <span className="adash-device-count">{c.demo_visitors} demo</span>
                      )}
                      <span className="adash-device-count">{c.visitors}</span>
                      <span className="adash-device-pct">{pct}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div>
            <div className="adash-geo-heading">Top cities</div>
            <div className="adash-devices">
              {cities.length === 0 && <div className="adash-empty">Unknown</div>}
              {cities.map((c) => (
                <div key={`${c.city}-${c.country_code}`} className="adash-device-row adash-geo-row">
                  <div className="adash-device-label">
                    <span className="adash-flag">{flagOf(c.country_code)}</span>
                    <span>{c.city}</span>
                    <span className="adash-geo-sub">{c.country}</span>
                  </div>
                  <div className="adash-device-stats">
                    <span className="adash-device-count">{c.visitors}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TopListsCard({ usage }) {
  const columns = [
    { title: "Companies viewed", rows: toPairs(usage.top_companies_viewed) },
    { title: "PDFs opened",      rows: toPairs(usage.top_pdfs_opened) },
    { title: "Error kinds",      rows: toPairs(usage.error_kinds) },
  ];
  if (!columns.some((c) => c.rows.length)) return null;

  return (
    <div className="adash-charts-row">
      {columns.map((col) => {
        const max = Math.max(...col.rows.map((r) => r[1]), 1);
        return (
          <div key={col.title} className="adash-card">
            <div className="adash-card-header">
              <span className="adash-card-title">{col.title}</span>
            </div>
            <div className="adash-devices">
              {col.rows.length === 0 && <div className="adash-empty">No data</div>}
              {col.rows.map(([name, count]) => (
                <div key={name} className="adash-device-row adash-geo-row">
                  <div className="adash-device-label">
                    <span className="adash-list-name" title={name}>{name}</span>
                  </div>
                  <div className="adash-device-stats">
                    <span className="adash-device-count">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Logins tab ───────────────────────────────────────────────────────────── */

function LoginsTab({ data }) {
  const { logins, login_log: log } = data;
  const attackers = (logins.top_bruteforce || []).filter((r) => r.failed > 0);

  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<UserIcon />}   label="Attempts"      value={logins.total_attempts} sub="every sign-in try" color="blue" />
        <KpiCard icon={<CheckIcon />}  label="Successful"    value={logins.total_success}  sub={`${logins.success_rate}% success rate`} color="teal" />
        <KpiCard icon={<LockIcon />}   label="Failed"        value={logins.total_failed}   sub="wrong credentials" color="rose" />
        <KpiCard icon={<AlertIcon />}  label="IPs Failing"   value={attackers.length}      sub="distinct sources" color="amber" />
      </div>

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Credentials tried</span>
          <span className="adash-card-sub">pass / fail split per account</span>
        </div>
        {(logins.by_email || []).length === 0 ? (
          <div className="adash-empty">No login attempt recorded yet</div>
        ) : (
          <div className="adash-table-wrap">
            <table className="adash-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th className="adash-num">Attempts</th>
                  <th className="adash-num">Success</th>
                  <th className="adash-num">Failed</th>
                  <th className="adash-num">Unique IPs</th>
                  <th>First seen</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {logins.by_email.map((r) => (
                  <tr key={r.email}>
                    <td className="adash-loc">{r.email}</td>
                    <td className="adash-num">{r.attempts}</td>
                    <td className="adash-num">{r.success}</td>
                    <td className={`adash-num ${r.failed ? "adash-num-hot" : ""}`}>{r.failed}</td>
                    <td className="adash-num">{r.unique_ips}</td>
                    <td className="adash-cell-muted">{formatWhen(r.first_seen)}</td>
                    <td className="adash-cell-muted">{formatWhen(r.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {attackers.length > 0 && (
        <div className="adash-card adash-abuse-card">
          <div className="adash-card-header">
            <span className="adash-card-title">
              <span className="adash-abuse-dot" />
              Failed sign-in attempts by IP
            </span>
            <span className="adash-card-sub">possible credential guessing</span>
          </div>
          <div className="adash-table-wrap">
            <table className="adash-table">
              <thead>
                <tr>
                  <th>IP address</th>
                  <th>Location</th>
                  <th className="adash-num">Failed</th>
                  <th>Last attempt</th>
                </tr>
              </thead>
              <tbody>
                {attackers.map((r) => (
                  <tr key={r.ip_hash}>
                    <td><code className="adash-ip">{r.ip || "—"}</code></td>
                    <td>
                      <span className="adash-flag">{flagOf("")}</span>
                      <span className="adash-loc">{r.location}</span>
                    </td>
                    <td className="adash-num adash-num-hot">{r.failed}</td>
                    <td className="adash-cell-muted">{formatWhen(r.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Login log</span>
          <span className="adash-card-sub">newest first</span>
        </div>
        <LogTable rows={log} />
      </div>
    </>
  );
}

function LogTable({ rows }) {
  if (!rows || rows.length === 0) return <div className="adash-empty">Nothing logged yet</div>;
  return (
    <div className="adash-table-wrap">
      <table className="adash-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Result</th>
            <th>Email</th>
            <th>IP address</th>
            <th>Location</th>
            <th>Via</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.ip_hash}-${r.ts}-${i}`}>
              <td className="adash-cell-muted">{formatWhen(r.ts)}</td>
              <td>
                <span className={`adash-chip ${r.ok ? "adash-chip-demo" : "adash-chip-fail"}`}>
                  {r.ok ? "success" : "failed"}
                </span>
              </td>
              <td className="adash-loc">{r.email || "—"}</td>
              <td><code className="adash-ip">{r.ip || "—"}</code></td>
              <td>{r.location}</td>
              <td className="adash-cell-muted">{r.kind || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Chat tab ─────────────────────────────────────────────────────────────── */

function ChatTab({ data }) {
  const { chat, questions } = data;
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return questions;
    return questions.filter((r) =>
      [r.question, r.company, r.location, r.role].some((v) =>
        String(v || "").toLowerCase().includes(q)
      )
    );
  }, [questions, query]);

  const counters = [
    { label: "Questions asked",    value: chat.total_questions },
    { label: "Unique askers",     value: chat.unique_askers },
    { label: "Per asker",         value: chat.questions_per_asker },
    { label: "Avg latency",       value: formatMs(chat.avg_latency_ms) },
    { label: "p50 latency",       value: formatMs(chat.p50_latency_ms) },
    { label: "p95 latency",       value: formatMs(chat.p95_latency_ms) },
    { label: "Max latency",       value: formatMs(chat.max_latency_ms) },
    { label: "With sources",      value: `${chat.source_rate ?? 0}%` },
    { label: "Error rate",        value: `${chat.error_rate ?? 0}%` },
  ];

  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<ChatIcon />}   label="Questions"    value={chat.total_questions} sub={`${chat.unique_askers ?? 0} askers`} color="amber" />
        <KpiCard icon={<UsersIcon />}  label="Per Visitor"  value={chat.questions_per_asker} sub="avg questions" color="blue" />
        <KpiCard icon={<ClockIcon />}  label="Avg Response" value={formatMs(chat.avg_latency_ms)} sub={`p95 ${formatMs(chat.p95_latency_ms)}`} color="teal" />
        <KpiCard icon={<CheckIcon />}  label="Answered"     value={`${chat.source_rate ?? 0}%`} sub="carried a citation" color="purple" />
      </div>

      <div className="adash-charts-row">
        <BarListCard title="Top companies asked about" rows={chat.top_companies} />
        <BarListCard title="Top years asked"          rows={chat.top_years} />
        <BarListCard title="Top sectors"              rows={chat.top_sectors} />
      </div>

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Question log</span>
          <div className="adash-search">
            <input
              className="adash-search-input"
              placeholder="Filter by question, company, location, role…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button className="adash-search-clear" onClick={() => setQuery("")} title="Clear">×</button>
            )}
          </div>
        </div>
        <div className="adash-card-sub adash-count-note">
          {filtered.length} of {questions.length} shown
        </div>
        <QuestionTable rows={filtered} />
      </div>

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Latency &amp; quality</span>
        </div>
        <div className="adash-metric-grid">
          {counters.map((c) => (
            <div key={c.label} className="adash-metric">
              <span className="adash-metric-val">{c.value ?? "—"}</span>
              <span className="adash-metric-lbl">{c.label}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function BarListCard({ title, rows = [] }) {
  const pairs = toPairs(rows);
  const max = Math.max(...pairs.map((r) => r[1]), 1);
  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">{title}</span>
      </div>
      <div className="adash-devices">
        {pairs.length === 0 && <div className="adash-empty">No data</div>}
        {pairs.map(([name, count]) => (
          <div key={name} className="adash-device-row">
            <div className="adash-device-label">
              <span className="adash-list-name" title={name}>{name}</span>
            </div>
            <div className="adash-device-bar-wrap">
              <div
                className="adash-device-bar-fill"
                style={{ width: `${(count / max) * 100}%`, background: "var(--adash-amber)" }}
              />
            </div>
            <div className="adash-device-stats">
              <span className="adash-device-count">{count}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function QuestionTable({ rows }) {
  if (!rows || rows.length === 0) return <div className="adash-empty">No question logged yet</div>;
  return (
    <div className="adash-table-wrap">
      <table className="adash-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Question</th>
            <th>Scope</th>
            <th>Role</th>
            <th>Location</th>
            <th>IP</th>
            <th className="adash-num">Time</th>
            <th className="adash-num">Src</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.ip_hash}-${r.ts}-${i}`}>
              <td className="adash-cell-muted">{timeOnly(r.ts)}</td>
              <td className="adash-question">{r.question || "—"}</td>
              <td className="adash-cell-muted">
                {r.company || "all reports"}
                {r.year ? ` · ${r.year}` : ""}
              </td>
              <td>
                {r.role ? (
                  <span className={`adash-chip ${r.role === "admin" ? "adash-chip-demo" : "adash-chip-desktop"}`}>
                    {r.role}
                  </span>
                ) : (
                  <span className="adash-cell-muted">—</span>
                )}
              </td>
              <td>{r.location}</td>
              <td><code className="adash-ip">{r.ip || "—"}</code></td>
              <td className="adash-num">{formatMs(r.latency_ms)}</td>
              <td className="adash-num">{r.sources ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Visitors tab ─────────────────────────────────────────────────────────── */

function VisitorsTab({ visitors }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("last_seen");
  const [expanded, setExpanded] = useState(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = visitors;
    if (q) {
      list = list.filter((v) =>
        [v.ip, v.location, v.isp, v.browser, v.os, v.role].some((val) =>
          String(val || "").toLowerCase().includes(q)
        )
      );
    }
    const sorted = [...list].sort((a, b) => {
      if (sort === "questions") return (b.questions || 0) - (a.questions || 0);
      if (sort === "failures") return (b.logins_fail || 0) - (a.logins_fail || 0);
      if (sort === "events")   return (b.total_events || 0) - (a.total_events || 0);
      return String(b.last_seen || "").localeCompare(String(a.last_seen || ""));
    });
    return sorted;
  }, [visitors, query, sort]);

  if (!visitors || visitors.length === 0) {
    return <div className="adash-card"><div className="adash-empty">No visitor data yet</div></div>;
  }

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Visitors — IP &amp; activity</span>
        <div className="adash-search">
          <input
            className="adash-search-input"
            placeholder="Filter IP, city, ISP, browser…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className="adash-select"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="last_seen">Most recent</option>
            <option value="questions">Most questions</option>
            <option value="failures">Most failed logins</option>
            <option value="events">Most events</option>
          </select>
        </div>
      </div>
      <div className="adash-card-sub adash-count-note">
        {rows.length} of {visitors.length} unique IPs
      </div>
      <div className="adash-table-wrap">
        <table className="adash-table">
          <thead>
            <tr>
              <th>Location</th>
              <th>IP address</th>
              <th>ISP</th>
              <th>Client</th>
              <th>Device</th>
              <th>Account</th>
              <th className="adash-num">Visits</th>
              <th className="adash-num">Logins</th>
              <th className="adash-num">Failed</th>
              <th className="adash-num">Qs</th>
              <th className="adash-num">PDFs</th>
              <th className="adash-num">Cos</th>
              <th>Span</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((v) => (
              <React.Fragment key={v.ip_hash}>
                <tr
                  className="adash-clickable"
                  onClick={() => setExpanded(expanded === v.ip_hash ? null : v.ip_hash)}
                >
                  <td>
                    <span className="adash-flag">{flagOf(v.country_code)}</span>
                    <span className="adash-loc">{v.location}</span>
                  </td>
                  <td><code className="adash-ip">{v.ip || "—"}</code></td>
                  <td className="adash-cell-muted adash-clip">{v.isp || "—"}</td>
                  <td className="adash-cell-muted adash-clip" title={`${v.browser || "?"} / ${v.os || "?"}`}>
                    {v.browser || "?"}{v.os ? ` · ${v.os}` : ""}
                  </td>
                  <td>
                    <span className={`adash-chip adash-chip-${v.device}`}>{v.device}</span>
                  </td>
                  <td>
                    {v.role ? (
                      <span className={`adash-chip ${v.role === "admin" ? "adash-chip-demo" : "adash-chip-desktop"}`}>
                        {v.role}
                      </span>
                    ) : (
                      <span className="adash-cell-muted">—</span>
                    )}
                  </td>
                  <td className="adash-num">{v.visits}</td>
                  <td className="adash-num">{v.logins_ok ?? 0}</td>
                  <td className={`adash-num ${v.logins_fail ? "adash-num-hot" : ""}`}>{v.logins_fail ?? 0}</td>
                  <td className="adash-num">{v.questions}</td>
                  <td className="adash-num">{v.pdf_opens}</td>
                  <td className="adash-num">{v.companies_explored}</td>
                  <td className="adash-cell-muted">{duration(v.first_seen, v.last_seen)}</td>
                  <td className="adash-cell-muted">{formatWhen(v.last_seen)}</td>
                </tr>
                {expanded === v.ip_hash && (
                  <tr className="adash-detail-row">
                    <td colSpan={14}>
                      <div className="adash-detail">
                        <div>
                          <span className="adash-detail-lbl">First seen</span>
                          <span className="adash-detail-val">{formatWhen(v.first_seen)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Sessions</span>
                          <span className="adash-detail-val">{v.sessions}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Total events</span>
                          <span className="adash-detail-val">{v.total_events}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Avg latency</span>
                          <span className="adash-detail-val">{formatMs(v.avg_latency_ms)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Demo messages</span>
                          <span className="adash-detail-val">{v.demo_messages}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Demo limit hits</span>
                          <span className="adash-detail-val">{v.demo_exhausted}</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Shared bits ──────────────────────────────────────────────────────────── */

function KpiCard({ icon, label, value, sub, color }) {
  return (
    <div className={`adash-kpi-card adash-kpi-${color}`}>
      <div className="adash-kpi-icon">{icon}</div>
      <div className="adash-kpi-body">
        <div className="adash-kpi-value">{value ?? 0}</div>
        <div className="adash-kpi-label">{label}</div>
        <div className="adash-kpi-sub">{sub}</div>
      </div>
    </div>
  );
}

function BarChart({ data, color }) {
  if (!data || data.length === 0) return <div className="adash-empty">No data</div>;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="adash-barchart">
      {data.map((d) => (
        <div key={d.date} className="adash-bar-col">
          <div className="adash-bar-tooltip">{d.count}</div>
          <div className="adash-bar-track">
            <div
              className="adash-bar-fill"
              style={{ height: `${(d.count / max) * 100}%`, background: color }}
            />
          </div>
          <div className="adash-bar-label">{d.day}</div>
        </div>
      ))}
    </div>
  );
}

function AbuseInsight({ exhausted, logins }) {
  const bypassRate = logins > 0 ? Math.round((exhausted / logins) * 100) : 0;
  const suspected = Math.max(0, exhausted - logins);
  return (
    <div className="adash-card adash-abuse-card">
      <div className="adash-card-header">
        <span className="adash-card-title">
          <span className="adash-abuse-dot" />
          Browser-Switch Detection
        </span>
        <span className="adash-card-sub">demo bypass analysis</span>
      </div>
      <div className="adash-abuse-grid">
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val">{exhausted}</span>
          <span className="adash-abuse-lbl">Times limit reached</span>
        </div>
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val">{logins}</span>
          <span className="adash-abuse-lbl">Demo logins total</span>
        </div>
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val adash-abuse-highlight">{bypassRate}%</span>
          <span className="adash-abuse-lbl">Exhaustion rate</span>
        </div>
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val adash-abuse-highlight">{suspected}</span>
          <span className="adash-abuse-lbl">Potential bypasses</span>
        </div>
      </div>
      <p className="adash-abuse-note">
        "Potential bypasses" = times the limit was hit beyond the number of distinct
        demo logins — each extra count likely means a new browser/private window was used
        to reset the localStorage counter.
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="adash-skeleton">
      <div className="adash-kpi-grid">
        {[0,1,2,3,4,5,6,7].map((i) => (
          <div key={i} className="adash-kpi-card adash-skeleton-card">
            <div className="sk-line sk-line-sm" />
            <div className="sk-line sk-line-lg" />
            <div className="sk-line sk-line-xs" />
          </div>
        ))}
      </div>
      <div className="adash-charts-row">
        <div className="adash-card adash-card-wide adash-skeleton-card" style={{height: 180}} />
        <div className="adash-card adash-card-wide adash-skeleton-card" style={{height: 180}} />
      </div>
      <div className="adash-card adash-skeleton-card" style={{height: 140}} />
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="adash-error">
      <svg viewBox="0 0 20 20" fill="none" width="32" height="32">
        <circle cx="10" cy="10" r="8.5" stroke="currentColor" strokeWidth="1.3"/>
        <path d="M10 6v5M10 13.5h.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
      </svg>
      <p>{message}</p>
      <button className="adash-retry-btn" onClick={onRetry}>Retry</button>
    </div>
  );
}

/* ── Icons ────────────────────────────────────────────────────────────────── */

function EyeIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <ellipse cx="8" cy="8" rx="6" ry="3.8" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="8" r="1.8" fill="currentColor"/>
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="6" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M1 14c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <circle cx="11.5" cy="4.5" r="2" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M13.5 13c0-1.9-1-3.5-2.5-4.3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M1.8 8h12.4M8 1.8c1.6 1.7 2.4 3.9 2.4 6.2S9.6 12.5 8 14.2C6.4 12.5 5.6 10.3 5.6 8s.8-4.5 2.4-6.2z" stroke="currentColor" strokeWidth="1.1"/>
    </svg>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="5" r="2.8" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5l-3 2V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M5 6h6M5 9h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function DocIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M9 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5.5L9 1.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M9 1.5V5a.5.5 0 0 0 .5.5H13M5.5 9h5M5.5 11.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function BuildingIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M2 14V3.5A1 1 0 0 1 3 2.5h5a1 1 0 0 1 1 1V14M9 7h3a1 1 0 0 1 1 1v6M1.5 14h13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4.5 5.5h1.5M4.5 8.5h1.5M4.5 11.5h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M8 2.2 14.3 13H1.7L8 2.2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11.5h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3"/>
      <path d="m5.2 8.2 2 2 3.6-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 5v3.5M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 4.5V8l2.4 1.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function DesktopIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
      <rect x="1" y="2" width="14" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5.5 14h5M8 11v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function MobileIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
      <rect x="4" y="1" width="8" height="14" rx="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="12.5" r=".8" fill="currentColor"/>
    </svg>
  );
}

function TabletIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
      <rect x="2" y="1" width="12" height="14" rx="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="12.5" r=".8" fill="currentColor"/>
    </svg>
  );
}
