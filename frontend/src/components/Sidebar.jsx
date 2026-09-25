import React, { useMemo, useState } from "react";

function initials(name) {
  return name
    .split(/[\s\-_]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

const SECTOR_MAP = {
  Banques:               "#3b82f6",
  Assurances:            "#8b5cf6",
  Télécommunications:    "#06b6d4",
  Mines:                 "#f59e0b",
  Immobilier:            "#10b981",
  Énergie:               "#ef4444",
  "Grande distribution": "#f97316",
  Agroalimentaire:       "#84cc16",
  Industrie:             "#6366f1",
};

// Short display labels for long sector names
const SECTOR_SHORT = {
  "Télécommunications": "Télécom",
  "Grande distribution": "Distrib.",
  "Agroalimentaire": "Agro",
};

function sectorColor(sector) {
  if (!sector) return "#94a3b8";
  for (const [key, color] of Object.entries(SECTOR_MAP)) {
    if (sector.toLowerCase().includes(key.toLowerCase())) return color;
  }
  return "#94a3b8";
}

function sectorLabel(sector) {
  return SECTOR_SHORT[sector] || sector;
}

export default function Sidebar({ companies, active, onSelect, onYearSelect, activeYear }) {
  const [search, setSearch]             = useState("");
  const [activeSector, setActiveSector] = useState("Tous");
  const [showSectors, setShowSectors]   = useState(true);
  const [showCompanies, setShowCompanies] = useState(true);

  const sectors = useMemo(() => {
    const set = new Set(companies.map((c) => c.sector || "Autre").filter(Boolean));
    return ["Tous", ...Array.from(set).sort((a, b) => a.localeCompare(b, "fr"))];
  }, [companies]);

  // Count per sector (unaffected by search so counts stay stable)
  const sectorCounts = useMemo(() => {
    const counts = { Tous: companies.length };
    for (const c of companies) {
      const s = c.sector || "Autre";
      counts[s] = (counts[s] || 0) + 1;
    }
    return counts;
  }, [companies]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return companies.filter((c) => {
      const matchSector = activeSector === "Tous" || (c.sector || "Autre") === activeSector;
      const matchSearch = !q || c.company.toLowerCase().includes(q);
      return matchSector && matchSearch;
    });
  }, [companies, search, activeSector]);

  // Group by sector when showing all with no search
  const grouped = useMemo(() => {
    const useGroups = activeSector === "Tous" && !search.trim();
    if (!useGroups) return [{ sector: null, items: filtered }];
    const map = new Map();
    for (const c of filtered) {
      const s = c.sector || "Autre";
      if (!map.has(s)) map.set(s, []);
      map.get(s).push(c);
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b, "fr"))
      .map(([sector, items]) => ({ sector, items }));
  }, [filtered, activeSector, search]);

  const activeCompany = companies.find((c) => c.company_normalized === active);

  return (
    <aside className="sidebar">

      {/* ── Header ── */}
      <button
        className="sidebar-header"
        onClick={() => setShowCompanies((v) => !v)}
        aria-expanded={showCompanies}
        title={showCompanies ? "Masquer les entreprises" : "Afficher les entreprises"}
      >
        <div className="sidebar-header-left">
          <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
            <rect x="1"  y="9"  width="4" height="6"  rx="1" fill="currentColor" opacity=".35"/>
            <rect x="6"  y="5"  width="4" height="10" rx="1" fill="currentColor" opacity=".65"/>
            <rect x="11" y="1"  width="4" height="14" rx="1" fill="currentColor"/>
          </svg>
          <p className="sidebar-label">Entreprises</p>
        </div>
        <div className="sidebar-header-right">
          <span className="sidebar-count">{filtered.length}</span>
          <svg
            viewBox="0 0 12 12" fill="none" width="10" height="10"
            style={{ transform: showCompanies ? "rotate(180deg)" : "rotate(0deg)", transition: "transform .2s", color: "var(--sidebar-muted)" }}
          >
            <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </button>

      {/* ── Collapsible body ── */}
      {showCompanies && (<>

      {/* ── Search ── */}
      <div className="sidebar-search-wrap">
        <svg className="sidebar-search-icon" viewBox="0 0 20 20" width="14" height="14" fill="none">
          <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M13 13l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
        <input
          className="sidebar-search"
          type="text"
          placeholder="Rechercher une entreprise…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button className="sidebar-clear" onClick={() => setSearch("")} aria-label="Effacer">
            <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
              <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        )}
      </div>

      {/* ── Sector filter ── */}
      <div className={`sector-filter-wrap ${showSectors ? "open" : "closed"}`}>
        <div className="sector-filter-head">
          <button
            className="sector-filter-toggle"
            onClick={() => setShowSectors((v) => !v)}
            aria-expanded={showSectors}
          >
            <span className="sector-filter-label">Secteur</span>
            {activeSector !== "Tous" && (
              <span className="sector-filter-active-dot" style={{ background: sectorColor(activeSector) }} />
            )}
            <svg
              viewBox="0 0 12 12" fill="none" width="10" height="10"
              style={{ transform: showSectors ? "rotate(180deg)" : "rotate(0deg)", transition: "transform .2s" }}
            >
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {activeSector !== "Tous" && showSectors && (
            <button
              className="sector-filter-reset"
              onClick={() => setActiveSector("Tous")}
            >
              Réinitialiser
            </button>
          )}
        </div>

        {showSectors && (
          <div className="sector-chips">
            {sectors.map((s) => {
              const color    = s !== "Tous" ? sectorColor(s) : null;
              const count    = sectorCounts[s] || 0;
              const isActive = activeSector === s;
              return (
                <button
                  key={s}
                  className={`sector-chip ${isActive ? "active" : ""}`}
                  onClick={() => setActiveSector(s)}
                  style={color ? { "--chip-color": color } : undefined}
                >
                  {color && (
                    <span className="sector-chip-dot" style={{ background: color }} />
                  )}
                  <span className="sector-chip-name">{sectorLabel(s)}</span>
                  {s !== "Tous" && (
                    <span className="sector-chip-count">{count}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Company list ── */}
      <div className="company-list">
        {filtered.length === 0 && (
          <div className="sidebar-empty-state">
            <svg viewBox="0 0 24 24" fill="none" width="32" height="32">
              <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M17 17l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <p>Aucune entreprise trouvée</p>
          </div>
        )}

        {grouped.map(({ sector, items }) => (
          <div key={sector || "__all"} className="company-group">

            {/* Sector group divider */}
            {sector && (
              <div className="company-group-header">
                <span className="company-group-dot" style={{ background: sectorColor(sector) }} />
                <span className="company-group-label">{sector}</span>
                <span className="company-group-count">{items.length}</span>
              </div>
            )}

            {items.map((c) => {
              const isActive = c.company_normalized === active;
              const color    = sectorColor(c.sector);
              const reports  = c.years?.length || 0;
              return (
                <div
                  key={c.company_normalized}
                  className={`company-item ${isActive ? "active" : ""}`}
                  style={{ "--sector-color": color }}
                >
                  <button
                    className="company-btn"
                    onClick={() => onSelect(c.company_normalized)}
                  >
                    <span className="company-avatar" style={{ background: color + "20", color }}>
                      {initials(c.company)}
                    </span>
                    <span className="company-info">
                      <span className="company-name">{c.company}</span>
                      {/* Show sector only when not grouped (search or single-sector filter) */}
                      {!sector && c.sector && (
                        <span className="company-meta">{c.sector}</span>
                      )}
                    </span>
                    <span className="company-reports-badge">{reports}</span>
                  </button>

                  {isActive && c.years?.length > 0 && (
                    <div className="year-row">
                      <button
                        className={`year-chip ${!activeYear ? "active" : ""}`}
                        onClick={() => onYearSelect(null)}
                      >
                        Tous
                      </button>
                      {c.years.map((y) => (
                        <button
                          key={y}
                          className={`year-chip ${activeYear === y ? "active" : ""}`}
                          onClick={() => onYearSelect(y)}
                        >
                          {y}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      </>)}

      {/* ── Active company footer ── */}
      {activeCompany && (
        <div className="sidebar-footer">
          <div className="sidebar-active-info">
            <span
              className="sidebar-active-dot"
              style={{ background: sectorColor(activeCompany.sector) }}
            />
            <span className="sidebar-active-name">{activeCompany.company}</span>
            {activeYear && (
              <span className="sidebar-active-year">{activeYear}</span>
            )}
          </div>
          <button
            className="clear-filter"
            onClick={() => { onSelect(null); onYearSelect(null); }}
            title="Désélectionner"
          >
            <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      )}
    </aside>
  );
}
