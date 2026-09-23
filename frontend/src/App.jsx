import React, { useEffect, useState } from "react";
import { fetchHealth, fetchCompanies, fetchReports } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import ChatPanel from "./components/ChatPanel.jsx";

export default function App() {
  const [health, setHealth]       = useState(null);
  const [companies, setCompanies] = useState([]);
  const [stats, setStats]         = useState(null);
  const [activeCompany, setActiveCompany] = useState(null);
  const [activeYear, setActiveYear]       = useState(null);
  const [sidebarOpen, setSidebarOpen]     = useState(true);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ ok: false }));
    fetchCompanies().then(setCompanies).catch(() => setCompanies([]));
    fetchReports().then((r) => setStats(r.total)).catch(() => {});
  }, []);

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
            <span className="brand-mark">A</span>
            <span className="brand-name">AMMC</span>
            <span className="brand-sep" />
            <span className="brand-sub">Intelligence Financière</span>
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
              <Stat label="entreprises" value={companies.length} />
              <Stat label="rapports" value={stats.rapports} />
              <Stat label="extraits" value={stats.chunks?.toLocaleString("fr")} />
            </div>
          )}
          <StatusBadge health={health} />
        </div>
      </header>

      <div className="layout">
        {/* ── Sidebar ── */}
        <div className={`sidebar-wrap ${sidebarOpen ? "open" : "closed"}`}>
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

        {/* ── Main ── */}
        <main className="main">
          <ChatPanel
            key={`${activeCompany}-${activeYear}`}
            company={activeCompany}
            companyName={selectedCompany?.company}
            year={activeYear}
            sector={selectedCompany?.sector}
          />
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
  const label = { up: "Index prêt", pending: "Connexion…", down: "Hors ligne" }[state];
  return (
    <span className={`status-badge ${state}`}>
      <span className="status-dot" />
      {label}
    </span>
  );
}
