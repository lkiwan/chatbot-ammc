import React, { useEffect, useState } from "react";
import { fetchHealth, fetchCompanies, fetchReports, trackEvent } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import PdfViewer from "./components/PdfViewer.jsx";
import Splitter from "./components/Splitter.jsx";
import Login from "./components/Login.jsx";
import AdminDashboard from "./components/AdminDashboard.jsx";
import useEdgeSwipe from "./useEdgeSwipe.js";

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
    if (raw) return JSON.parse(raw);
  } catch {}
}

function useIsMobile() {
  const mq = window.matchMedia("(max-width: 860px)");
  const [isMobile, setIsMobile] = useState(() => mq.matches);
  useEffect(() => {
    const on = () => setIsMobile(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [mq]);
  return isMobile;
}

export default function App() {
  const [auth, setAuth] = useState(loadSession);
  const [adminView, setAdminView] = useState(false);
  const isMobile = useIsMobile();

  const [health, setHealth]       = useState(null);
  const [companies, setCompanies] = useState([]);
  const [stats, setStats]         = useState(null);
  const [activeCompany, setActiveCompany] = useState(null);
  const [activeYear, setActiveYear]       = useState(null);
  const [sidebarOpen, setSidebarOpen]     = useState(() => !window.matchMedia("(max-width: 860px)").matches);
  const [pdfOpen, setPdfOpen]             = useState(() => !window.matchMedia("(max-width: 860px)").matches);
  const [activeSource, setActiveSource]   = useState(null);
  const [sizes, setSizes]         = useState(loadSizes);

  // Touch-only: swipe in from the left edge toggles the menu, from the right
  // edge toggles the PDF viewer. Swiping back the other way closes an open
  // panel. Progress is "openness" 0 -> 1 so the panels track the finger in
  // both directions instead of snapping.
  const swipe = useEdgeSwipe({
    enabled: isMobile && !adminView && !!auth,
    startOpen: sidebarOpen,
    endOpen: pdfOpen,
    width: isMobile ? window.innerWidth * 0.82 : 0,
    onToggleStart: () => setSidebarOpen((v) => !v),
    onToggleEnd: () => setPdfOpen((v) => !v),
  });
  const swipeProgress = swipe.progress;

  // "Openness" for each panel: the live drag while a swipe is in flight,
  // otherwise the committed open/closed state.
  const menuOpenness =
    swipe.edge === "start" ? swipeProgress : sidebarOpen ? 1 : 0;
  const pdfOpenness =
    swipe.edge === "end" ? swipeProgress : pdfOpen ? 1 : 0;

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

  // Which company a visitor actually opens is the best proxy for what they
  // came to analyse, so it is logged separately from the questions they ask.
  useEffect(() => {
    if (!auth || !activeCompany) return;
    const company = companies.find((c) => c.company_normalized === activeCompany);
    trackEvent("company_select", auth.role, {
      company: company?.company || activeCompany,
      year: activeYear ? String(activeYear) : "",
      sector: company?.sector || "",
    });
    // companies is intentionally excluded: the selection is the trigger, and
    // re-firing when the list loads would log the same choice twice.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth, activeCompany, activeYear]);

  // One visit per page load, so reloads and anonymous browsing are counted.
  // The session (if any) is already in sessionStorage at mount time.
  useEffect(() => {
    trackEvent("visit", loadSession()?.role || "");
  }, []);

  const handleLogin = (authData) => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(authData));
    setAuth(authData);
  };

  const handleLogout = () => {
    trackEvent("logout", auth?.role || "");
    sessionStorage.removeItem(SESSION_KEY);
    setAdminView(false);
    setAuth(null);
    setCompanies([]);
    setStats(null);
    setHealth(null);
    setActiveCompany(null);
    setActiveYear(null);
  };

  if (!auth) return <Login onLogin={handleLogin} />;

  const selectedCompany = companies.find((c) => c.company_normalized === activeCompany);

  const sidebarContent = companies.length > 0 ? (
    <Sidebar
      companies={companies}
      active={activeCompany}
      activeYear={activeYear}
      onSelect={(slug) => {
        setActiveCompany(slug);
        setActiveYear(null);
      }}
      onYearSelect={(y) => {
        setActiveYear(y);
        if (isMobile) setSidebarOpen(false);
      }}
    />
  ) : (
    <div className="sidebar-loading">
      <div className="skeleton-line" />
      <div className="skeleton-line short" />
      <div className="skeleton-line" />
      <div className="skeleton-line short" />
    </div>
  );

  return (
    <div className="app">
      {/* Edge affordances: hint where an edge swipe is armed */}
      {isMobile && !sidebarOpen && !pdfOpen && (
        <span className="edge-hint edge-hint-left" aria-hidden="true" />
      )}
      {isMobile && !pdfOpen && (
        <span className="edge-hint edge-hint-right" aria-hidden="true" />
      )}

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
            <img src="/logo.png" alt="AnnualEdge" className="brand-logo" />
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
            {auth.role === "admin" && (
              <button
                className={`btn-dashboard ${adminView ? "active" : ""}`}
                onClick={() => setAdminView((v) => !v)}
                title="Analytics Dashboard"
              >
                <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
                  <rect x="1" y="9" width="3" height="5" rx=".8" fill="currentColor" opacity=".6"/>
                  <rect x="6" y="5" width="3" height="9" rx=".8" fill="currentColor" opacity=".8"/>
                  <rect x="11" y="1" width="3" height="13" rx=".8" fill="currentColor"/>
                </svg>
                Dashboard
              </button>
            )}
            <span className="topbar-user-role">
              {auth.role === "admin"
                ? "Admin"
                : auth.role === "user"
                  ? (auth.full_name?.split(" ")[0] || "User")
                  : "Demo"}
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
        {!isMobile && (
          <>
            {/* ── Sidebar (desktop) ── */}
            <div className={`sidebar-wrap ${sidebarOpen ? "open" : "closed"}`}
              style={{ width: sidebarOpen ? sizes.sidebar : 0 }}
            >
              {sidebarContent}
            </div>

            {sidebarOpen && (
              <Splitter
                orientation="vertical"
                onResize={(d) =>
                  setSizes((s) => ({ ...s, sidebar: clamp(s.sidebar + d, 200, 420) }))
                }
              />
            )}
          </>
        )}

        {/* ── Mobile menu (drawer) ── */}
        {/* While a swipe is in flight the drag owns the transform; otherwise fall
            back to the committed state so the panel is never stranded. */}
        {isMobile && (sidebarOpen || (swipe.edge === "start" && swipeProgress > 0)) && (
          <div
            className="mobile-nav"
            role="dialog"
            aria-modal="true"
            style={{ opacity: menuOpenness, pointerEvents: menuOpenness > 0.6 ? "auto" : "none" }}
          >
            <div
              className="mobile-nav-scrim"
              style={{ opacity: menuOpenness }}
              onClick={() => {
                // Ignore the click that ends an edge swipe: the swipe already
                // decided what should happen, and closing here too would make
                // a swipe from the far edge just dismiss this panel.
                if (swipe.shouldSwallowClick) return;
                setSidebarOpen(false);
              }}
            />
            <div
              className="mobile-nav-panel"
              style={{
                transform: `translateX(${(1 - menuOpenness) * -100}%)`,
                transition: swipe.edge === "start" ? "none" : "transform .25s cubic-bezier(.22,1,.36,1)",
              }}
            >
              <div className="mobile-nav-head">
                <img src="/logo.png" alt="AnnualEdge" className="mobile-nav-logo" />
                <span className="mobile-nav-title">AnnualEdge</span>
                <button
                  className="mobile-nav-close"
                  onClick={() => setSidebarOpen(false)}
                  aria-label="Fermer le menu"
                >
                  <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                    <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
              {sidebarContent}
            </div>
          </div>
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
            isDemo={auth?.role === "demo"}
            userToken={auth?.role === "user" ? auth?.token || "" : ""}
            pdfOpen={pdfOpen}
            onTogglePdf={() => setPdfOpen((v) => !v)}
          />

          {(!isMobile || pdfOpen || (swipe.edge === "end" && swipeProgress > 0)) && (
            <>
              <Splitter
                orientation="vertical"
                onResize={(d) =>
                  setSizes((s) => ({ ...s, pdf: clamp(s.pdf - d, 280, 980) }))
                }
              />
              <div
                className="pdf-right-wrap"
                style={{
                  width: isMobile ? "100%" : sizes.pdf,
                  // slide in from the right as the finger drags left, and back
                  // out again when the same edge is swiped to dismiss
                  transform:
                    isMobile ? `translateX(${(1 - pdfOpenness) * 100}%)` : undefined,
                  transition:
                    swipe.edge === "end" ? "none" : "transform .25s cubic-bezier(.22,1,.36,1)",
                }}
              >
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

      {adminView && auth.role === "admin" && (
        <AdminDashboard onClose={() => setAdminView(false)} />
      )}
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
