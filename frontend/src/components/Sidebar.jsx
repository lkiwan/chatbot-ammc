import React, { useMemo, useState } from "react";

function initials(name) {
  return name
    .split(/[\s\-_]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function sectorColor(sector) {
  const map = {
    Banques:          "#3b82f6",
    Assurances:       "#8b5cf6",
    Télécommunications: "#06b6d4",
    Mines:            "#f59e0b",
    Immobilier:       "#10b981",
    Énergie:          "#ef4444",
    "Grande distribution": "#f97316",
    Agroalimentaire:  "#84cc16",
    Industrie:        "#6366f1",
  };
  if (!sector) return "#94a3b8";
  for (const [key, color] of Object.entries(map)) {
    if (sector.toLowerCase().includes(key.toLowerCase())) return color;
  }
  return "#94a3b8";
}

export default function Sidebar({ companies, active, onSelect, onYearSelect, activeYear }) {
  const [search, setSearch] = useState("");
  const [activeSector, setActiveSector] = useState("Tous");
  const [showFilters, setShowFilters] = useState(true);

  const sectors = useMemo(() => {
    const set = new Set(companies.map((c) => c.sector || "Autre").filter(Boolean));
    return ["Tous", ...Array.from(set).sort()];
  }, [companies]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return companies.filter((c) => {
      const matchSector = activeSector === "Tous" || (c.sector || "Autre") === activeSector;
      const matchSearch = !q || c.company.toLowerCase().includes(q);
      return matchSector && matchSearch;
    });
  }, [companies, search, activeSector]);

  const activeCompany = companies.find((c) => c.company_normalized === active);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <p className="sidebar-label">Entreprises</p>
        <span className="sidebar-count">{filtered.length}</span>
      </div>

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
          <button className="sidebar-clear" onClick={() => setSearch("")} aria-label="Effacer">×</button>
        )}
      </div>

      <div className="sector-filter-head">
        <button
          className={`sector-filter-toggle ${activeSector !== "Tous" ? "has-filter" : ""}`}
          onClick={() => setShowFilters((v) => !v)}
          aria-expanded={showFilters}
        >
          <span className="sector-filter-label">
            Filtres
            {showFilters ? " ▾" : " ▸"}
          </span>
          {activeSector !== "Tous" && (
            <span
              className="sector-reset"
              onClick={(e) => { e.stopPropagation(); setActiveSector("Tous"); }}
              role="button"
              aria-label="Réinitialiser le filtre"
            >
              ×
            </span>
          )}
        </button>
      </div>

      {showFilters && (
        <div className="sector-chips">
          {sectors.map((s) => (
            <button
              key={s}
              className={`sector-chip ${activeSector === s ? "active" : ""}`}
              onClick={() => setActiveSector(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="company-list">
        {filtered.length === 0 && (
          <p className="sidebar-empty">Aucune entreprise trouvée</p>
        )}
        {filtered.map((c) => {
          const isActive = c.company_normalized === active;
          const color = sectorColor(c.sector);
          return (
            <div key={c.company_normalized} className={`company-item ${isActive ? "active" : ""}`}>
              <button
                className="company-btn"
                onClick={() => onSelect(c.company_normalized)}
              >
                <span className="company-avatar" style={{ background: color + "22", color }}>
                  {initials(c.company)}
                </span>
                <span className="company-info">
                  <span className="company-name">{c.company}</span>
                  <span className="company-meta">
                    {c.sector || ""}
                    {c.years?.length ? ` · ${c.years.length} rapport${c.years.length > 1 ? "s" : ""}` : ""}
                  </span>
                </span>
                {isActive && (
                  <span className="company-active-dot" />
                )}
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

      {active && (
        <div className="sidebar-footer">
          <button className="clear-filter" onClick={() => { onSelect(null); onYearSelect(null); }}>
            <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Tous les rapports
          </button>
        </div>
      )}
    </aside>
  );
}
