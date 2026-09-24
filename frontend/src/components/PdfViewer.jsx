import React, { useEffect, useMemo, useState } from "react";
import { fetchPdfs } from "../api.js";

const proxied = (url, page) => {
  const base = `/api/pdf?url=${encodeURIComponent(url)}`;
  return page ? `${base}#page=${page}` : base;
};

const cleanLabel = (label) =>
  typeof label === "string" ? label.replace(/,\s*p\.?\s*\d+$/i, "") : "";

export default function PdfViewer({ source, company, year, onClose }) {
  const [pdfs, setPdfs] = useState([]);
  const [current, setCurrent] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    fetchPdfs().then(setPdfs).catch(() => setPdfs([]));
  }, []);

  useEffect(() => {
    setCurrent(null);
    setMenuOpen(false);
  }, [company, year]);

  useEffect(() => {
    if (source?.url) {
      setCurrent({ url: source.url, label: source.label || "Document", page: source.page || 1 });
      setMenuOpen(false);
    }
  }, [source]);

  const visiblePdfs = useMemo(
    () =>
      pdfs.filter(
        (p) =>
          (!company || p.company_normalized === company) &&
          (!year || String(p.year) === String(year))
      ),
    [pdfs, company, year]
  );

  const openPdf = (p) => {
    setCurrent({
      url: p.url,
      label: p.company ? `${p.company}${p.year ? ` ${p.year}` : ""}`.trim() : p.stem,
      page: 1,
    });
    setMenuOpen(false);
  };

  return (
    <aside className="pdf-right">
      <div className="pdf-right-head">
        <div className="pdf-right-title-wrap">
          <span className="pdf-right-title">
            {current ? cleanLabel(current.label) : "Visionneuse PDF"}
          </span>
          {current?.page && <span className="pdf-right-page">p.{current.page}</span>}
        </div>
        <div className="pdf-right-actions">
          <div className="pdf-picker">
            <button
              className="pdf-picker-btn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              aria-label="Choisir un PDF"
            >
              <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
                <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            {menuOpen && (
              <div className="pdf-picker-menu">
                {visiblePdfs.length === 0 && (
                  <p className="pdf-picker-empty">
                    Aucun PDF indexé{company ? " pour cette entreprise" : ""}.
                  </p>
                )}
                {visiblePdfs.map((p) => (
                  <button key={p.stem} className="pdf-picker-item" onClick={() => openPdf(p)}>
                    <span className="pdf-picker-year">{p.year}</span>
                    <span className="pdf-picker-name">{p.company}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {current && (
            <a
              className="pdf-ext"
              href={`${current.url}#page=${current.page || 1}`}
              target="_blank"
              rel="noreferrer"
              title="Ouvrir dans un nouvel onglet"
            >
              ↗
            </a>
          )}
          <button className="pdf-close" onClick={onClose} title="Fermer le panneau PDF">
            ×
          </button>
        </div>
      </div>

      {current ? (
        <iframe
          key={`${current.url}#page=${current.page || 1}`}
          className="pdf-right-frame"
          src={proxied(current.url, current.page)}
          title="Document PDF"
        />
      ) : (
        <div className="pdf-right-empty">
          <div className="pdf-right-empty-icon">
            <svg viewBox="0 0 24 24" fill="none" width="30" height="30">
              <path d="M7 3h7l4 4v14H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
              <path d="M14 3v4h4M10 12h5M10 15h5M10 9h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <p>
            Cliquez sur une <strong>source</strong> dans le chat
            (ex. « ATTIJARIWAFA_BANK, p.12 ») pour afficher la page du rapport ici.
          </p>
          <p className="pdf-right-empty-sub">
            Ou choisissez un rapport via le menu PDFs en haut de ce panneau.
          </p>
        </div>
      )}
    </aside>
  );
}