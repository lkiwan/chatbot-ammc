import React, { useEffect, useMemo, useState } from "react";
import { fetchTables } from "../api.js";

export default function DataExplorer() {
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [pageFilter, setPageFilter] = useState("all");

  useEffect(() => {
    fetchTables()
      .then(setTables)
      .catch(() => setTables([]))
      .finally(() => setLoading(false));
  }, []);

  const pages = useMemo(
    () => [...new Set(tables.map((t) => t.page))].sort((a, b) => a - b),
    [tables]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tables.filter((t) => {
      if (pageFilter !== "all" && t.page !== pageFilter) return false;
      if (!q) return true;
      return t.rows.some((r) => r.join(" ").toLowerCase().includes(q));
    });
  }, [tables, query, pageFilter]);

  return (
    <div className="explorer">
      <div className="explorer-bar">
        <input
          className="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher dans les tableaux… (ex. actionnaires)"
        />
        <select
          className="page-select"
          value={pageFilter}
          onChange={(e) => setPageFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
        >
          <option value="all">Toutes les pages</option>
          {pages.map((p) => (
            <option key={p} value={p}>
              Page {p}
            </option>
          ))}
        </select>
        <span className="count">{filtered.length} tableaux</span>
      </div>

      {loading ? (
        <p className="muted">Lecture du fichier extrait…</p>
      ) : filtered.length === 0 ? (
        <p className="muted">Aucun tableau ne correspond à cette recherche.</p>
      ) : (
        <div className="table-list">
          {filtered.map((t, i) => (
            <article className="table-card" key={i}>
              <header className="table-card-head">
                <span className="page-pill">p. {t.page}</span>
                <span className="table-id">Tableau n° {t.table}</span>
              </header>
              <div className="table-scroll">
                <table className="data-table">
                  <tbody>
                    {t.rows.slice(0, 12).map((row, j) => (
                      <tr key={j}>
                        {row.map((cell, k) => (
                          <td key={k}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {t.rows.length > 12 && (
                <p className="truncated">… {t.rows.length - 12} lignes supplémentaires</p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}