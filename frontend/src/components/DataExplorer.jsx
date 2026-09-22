import React, { useEffect, useMemo, useState } from "react";
import { fetchTables, reingest } from "../api.js";

export default function DataExplorer({ onRefresh, reportsCount = 0 }) {
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [query, setQuery] = useState("");
  const [rapportFilter, setRapportFilter] = useState("all");
  const [pageFilter, setPageFilter] = useState("all");

  const load = () => {
    setLoading(true);
    fetchTables()
      .then(setTables)
      .catch(() => setTables([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, [reportsCount]);

  const rapports = useMemo(
    () => [...new Set(tables.map((t) => t.rapport))].sort(),
    [tables]
  );

  const pages = useMemo(
    () => [...new Set(tables.map((t) => t.page))].sort((a, b) => a - b),
    [tables]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tables.filter((t) => {
      if (rapportFilter !== "all" && t.rapport !== rapportFilter) return false;
      if (pageFilter !== "all" && t.page !== pageFilter) return false;
      if (!q) return true;
      return t.rows.some((r) => r.join(" ").toLowerCase().includes(q));
    });
  }, [tables, query, rapportFilter, pageFilter]);

  const reindex = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const r = await reingest();
      setMessage(
        r.added > 0
          ? `Nouveaux rapports indexés : ${r.added}`
          : "Rien de nouveau — tous les PDF sont déjà indexés."
      );
      load();
      if (onRefresh) onRefresh();
    } catch (e) {
      setMessage(`Erreur : ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

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
          value={rapportFilter}
          onChange={(e) => setRapportFilter(e.target.value)}
        >
          <option value="all">Tous les rapports</option>
          {rapports.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
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
        <button className="btn btn-ghost reindex" onClick={reindex} disabled={busy}>
          {busy ? "Analyse…" : "Ré-extraire les PDF"}
        </button>
      </div>

      {message && <p className="ingest-msg">{message}</p>}

      {loading ? (
        <p className="muted">Lecture des fichiers extraits…</p>
      ) : filtered.length === 0 ? (
        <p className="muted">Aucun tableau ne correspond à cette recherche.</p>
      ) : (
        <div className="table-list">
          {filtered.map((t, i) => (
            <article className="table-card" key={i}>
              <header className="table-card-head">
                <span className="page-pill">p. {t.page}</span>
                <span className="table-report">{t.rapport}</span>
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