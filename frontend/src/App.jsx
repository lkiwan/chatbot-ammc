import React, { useEffect, useState } from "react";
import { fetchHealth, fetchCompanies, fetchReports } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import PdfViewer from "./components/PdfViewer.jsx";
import Splitter from "./components/Splitter.jsx";

const LS_KEY = "ammc-layout";

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

export default function App() {
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
    fetchHealth().then(setHealth).catch(() => setHealth({ ok: false }));
    fetchCompanies().then(setCompanies).catch(() => setCompanies([]));
    fetchReports().then((r) => setStats(r.total)).catch(() => {});
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(sizes));
    } catch {}
  }, [sizes]);

  useEffect(() => {
    setActiveSource(null);
  }, [activeCompany, activeYear]);

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
          <button
            className={`btn-pdf-toggle ${pdfOpen ? "active" : ""}`}
            onClick={() => setPdfOpen((v) => !v)}
            aria-pressed={pdfOpen}
            title="Afficher / masquer la visionneuse PDF"
          >
            PDF
          </button>
          <StatusBadge health={health} />
        </div>
      </header>

      <div className="layout">
        {/* ── Menu (entreprises) ── */}
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

        {/* ── Chat + visionneuse PDF ── */}
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
  const label = { up: "Index prêt", pending: "Connexion…", down: "Hors ligne" }[state];
  return (
    <span className={`status-badge ${state}`}>
      <span className="status-dot" />
      {label}
    </span>
  );
}