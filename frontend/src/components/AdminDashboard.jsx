import React, { useEffect, useState, useCallback } from "react";
import { fetchAnalytics } from "../api.js";

const REFRESH_MS = 30_000;

export default function AdminDashboard({ onClose }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(() => {
    fetchAnalytics()
      .then((d) => {
        setData(d);
        setError(null);
        setLastUpdated(new Date());
      })
      .catch(() => setError("Failed to load analytics."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="adash-overlay">
      <div className="adash-container">
        {/* Header */}
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
            <button className="adash-close" onClick={onClose} title="Close dashboard">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="adash-body">
          {loading && <LoadingSkeleton />}
          {error && !loading && <ErrorState message={error} onRetry={load} />}
          {data && !loading && <DashboardContent data={data} />}
        </div>
      </div>
    </div>
  );
}

function DashboardContent({ data }) {
  const {
    total_visits,
    unique_visitors_30d,
    total_demo_logins,
    total_demo_messages,
    total_demo_exhausted,
    device_breakdown,
    visits_per_day,
    demo_logins_per_day,
    demo_exhausted_per_day,
  } = data;

  const totalDevices = Object.values(device_breakdown).reduce((s, v) => s + v, 0);

  return (
    <>
      {/* KPI Cards */}
      <div className="adash-kpi-grid">
        <KpiCard
          icon={<EyeIcon />}
          label="Total Visits"
          value={total_visits}
          sub="all time"
          color="blue"
        />
        <KpiCard
          icon={<UsersIcon />}
          label="Unique Visitors"
          value={unique_visitors_30d}
          sub="last 30 days"
          color="purple"
        />
        <KpiCard
          icon={<UserIcon />}
          label="Demo Logins"
          value={total_demo_logins}
          sub="all time"
          color="teal"
        />
        <KpiCard
          icon={<ChatIcon />}
          label="Demo Messages"
          value={total_demo_messages}
          sub="all time"
          color="amber"
        />
        <KpiCard
          icon={<ExhaustedIcon />}
          label="Demo Limit Hit"
          value={total_demo_exhausted ?? 0}
          sub="browser switches suspected"
          color="rose"
        />
      </div>

      {/* Demo abuse insight */}
      {(total_demo_exhausted ?? 0) > 0 && (
        <AbuseInsight
          exhausted={total_demo_exhausted ?? 0}
          logins={total_demo_logins}
        />
      )}

      {/* Charts Row */}
      <div className="adash-charts-row">
        {/* Visits Bar Chart */}
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Visits — Last 7 Days</span>
          </div>
          <BarChart data={visits_per_day} color="var(--adash-blue)" />
        </div>

        {/* Demo Logins Bar Chart */}
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Demo Logins — Last 7 Days</span>
          </div>
          <BarChart data={demo_logins_per_day} color="var(--adash-teal)" />
        </div>

        {/* Demo Exhausted Bar Chart */}
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Demo Limit Reached — Last 7 Days</span>
          </div>
          <BarChart data={demo_exhausted_per_day ?? []} color="var(--adash-rose)" />
        </div>
      </div>

      {/* Device Breakdown */}
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
            const count = device_breakdown[key] ?? 0;
            const pct = totalDevices > 0 ? Math.round((count / totalDevices) * 100) : 0;
            return (
              <div key={key} className="adash-device-row">
                <div className="adash-device-label">
                  <span className="adash-device-icon">{icon}</span>
                  <span>{label}</span>
                </div>
                <div className="adash-device-bar-wrap">
                  <div
                    className="adash-device-bar-fill"
                    style={{ width: `${pct}%`, background: color }}
                  />
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
    </>
  );
}

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
  if (!data || data.length === 0) {
    return <div className="adash-empty">No data</div>;
  }
  const max = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="adash-barchart">
      {data.map((d) => {
        const heightPct = (d.count / max) * 100;
        return (
          <div key={d.date} className="adash-bar-col">
            <div className="adash-bar-tooltip">{d.count}</div>
            <div className="adash-bar-track">
              <div
                className="adash-bar-fill"
                style={{ height: `${heightPct}%`, background: color }}
              />
            </div>
            <div className="adash-bar-label">{d.day}</div>
          </div>
        );
      })}
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
        {[0,1,2,3].map((i) => (
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

// ── Icons ─────────────────────────────────────────────────────────────────────

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

function ExhaustedIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <rect x="3" y="7.5" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5.5 7.5V5a2.5 2.5 0 0 1 5 0v2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M8 10v2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
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
