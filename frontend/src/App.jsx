import React, { useEffect, useState } from "react";
import { fetchHealth, fetchCompanies, fetchReports } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import PdfViewer from "./components/PdfViewer.jsx";
import Splitter from "./components/Splitter.jsx";
import Login from "./components/Login.jsx";

const LS_KEY      = "ammc-layout";
const SESSION_KEY = "ae-session";

const clamp = (v, min, max) => Math.min(Math.max(v, min), max);

function loadSizes() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
      const s = JSON.parse(raw);
      if (typeof s.sidebar === "number" && typeof s.pdf === "number") return s;
    }
  } catch {}
  return { sidebar: 272, pdf: 400 };
}

function loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export default function App() {
  const [auth, setAuth] = useState(loadSession);

  const [health, setHealth]       = useState(null);
  const [companies, setCompanies] = useState([]);
  const [stats, setStats]         = useState(null);
  const [activeCompany, setActiveCompany] = useState(null);
  const [activeYear, setActiveYear]       = useState(null);
  const [sidebarOpen, setSidebarOpen]     = useState(true);
  const [pdfOpen, setPdfOpen]             = useState(true);
  const [activeSource, setActiveSource]   = useState(null);
  const [sizes, setSizes]         = useState(loadSizes);

  useEffect(() => {
    if (!auth) return;
    fetchHealth().then(setHealth).catch(() => setHealth({ ok: false }));
    fetchCompanies().then(setCompanies).catch(() => setCompanies([]));
    fetchReports().then((r) => setStats(r.total)).catch(() => {});
  }, [auth]);

  useEffect(() => {
    try { localStorage.setItem(LS_KEY, JSON.stringify(sizes)); } catch {}
  }, [sizes]);

  useEffect(() => {
    setActiveSource(null);
  }, [activeCompany, activeYear]);

  const handleLogin = (authData) => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(authData));
    setAuth(authData);
  };

  const handleLogout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    setAuth(null);
    setCompanies([]);
    setStats(null);
    setHealth(null);
    setActiveCompany(null);
    setActiveYear(null);
  };

  if (!auth) return <Login onLogin={handleLogin} />;

  const selectedCompany = companies.find((c) => c.company_normalized === activeCompany);

  return (
    <div className="app">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="topbar-menu"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Toggle sidebar"
          >
            <span /><span /><span />
          </button>
          <div className="brand">
            <span className="brand-mark">AE</span>
            <span className="brand-name">AnnualEdge</span>
            <span className="brand-sep" />
            <span className="brand-sub">Financial Intelligence</span>
          </div>
        </div>

        <div className="topbar-center">
          {selectedCompany && (
            <div className="topbar-context">
              <span className="topbar-company">{selectedCompany.company}</span>
              {activeYear && <span className="topbar-year">{activeYear}</span>}
            </div>
          )}
        </div>

        <div className="topbar-right">
          {stats && (
            <div className="topbar-stats">
              <Stat label="companies" value={companies.length} />
              <Stat label="reports"   value={stats.rapports} />
              <Stat label="excerpts"  value={stats.chunks?.toLocaleString("fr")} />
            </div>
          )}
          <button
            className={`btn-pdf-toggle ${pdfOpen ? "active" : ""}`}
            onClick={() => setPdfOpen((v) => !v)}
            aria-pressed={pdfOpen}
            title="Show / hide PDF viewer"
          >
            PDF
          </button>
          <StatusBadge health={health} />
          <div className="topbar-user">
            <span className="topbar-user-role">
              {auth.role === "admin" ? "Admin" : "Demo"}
            </span>
            <button className="btn-logout" onClick={handleLogout} title="Sign out">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3M10 11l3-3-3-3M13 8H6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </header>

      <div className="layout">
        {/* ── Sidebar ── */}
        <div className={`sidebar-wrap ${sidebarOpen ? "open" : "closed"}`}
          style={{ width: sidebarOpen ? sizes.sidebar : 0 }}
        >
          {companies.length > 0 && (
            <Sidebar
              companies={companies}
              active={activeCompany}
              activeYear={activeYear}
              onSelect={(slug) => { setActiveCompany(slug); setActiveYear(null); }}
              onYearSelect={setActiveYear}
            />
          )}
          {companies.length === 0 && (
            <div className="sidebar-loading">
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
            </div>
          )}
        </div>

        {sidebarOpen && (
          <Splitter
            orientation="vertical"
            onResize={(d) =>
              setSizes((s) => ({ ...s, sidebar: clamp(s.sidebar + d, 200, 420) }))
            }
          />
        )}

        {/* ── Chat + PDF viewer ── */}
        <main className="main">
          <ChatPanel
            key={`${activeCompany}-${activeYear}`}
            company={activeCompany}
            companyName={selectedCompany?.company}
            year={activeYear}
            sector={selectedCompany?.sector}
            onOpenSource={setActiveSource}
          />

          {pdfOpen && (
            <>
              <Splitter
                orientation="vertical"
                onResize={(d) =>
                  setSizes((s) => ({ ...s, pdf: clamp(s.pdf - d, 280, 980) }))
                }
              />
              <div className="pdf-right-wrap" style={{ width: sizes.pdf }}>
                <PdfViewer
                  source={activeSource}
                  company={activeCompany}
                  year={activeYear}
                  onClose={() => setPdfOpen(false)}
                />
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="topbar-stat">
      <span className="topbar-stat-value">{value ?? "—"}</span>
      <span className="topbar-stat-label">{label}</span>
    </div>
  );
}

function StatusBadge({ health }) {
  const state = health === null ? "pending" : health?.index ? "up" : "down";
  const label = { up: "Ready", pending: "Connecting…", down: "Offline" }[state];
  return (
    <span className={`status-badge ${state}`}>
      <span className="status-dot" />
      {label}
    </span>
  );
}
