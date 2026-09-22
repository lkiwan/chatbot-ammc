import React from "react";
import { niceName } from "../format.js";

export default function ReportPicker({ rapports = [], active, onSelect, total }) {
  return (
    <section className="instruments wrap reveal">
      <div className="instruments-head">
        <p className="eyebrow">Instruments en base</p>
        <h2>
          {total?.rapports ?? 0} instrument{total?.rapports > 1 ? "s" : ""} disponible
          {total?.rapports > 1 ? "s" : ""}
        </h2>
        <p className="instruments-sub">
          Choisissez un rapport pour l’interroger dans une session dédiée. Cliquer crée
          une nouvelle conversation.
        </p>
      </div>

      <div className="instrument-grid">
        <button
          className={`instrument ${active === null ? "active" : ""}`}
          onClick={() => onSelect(null)}
        >
          <span className="instrument-name">Tous les rapports</span>
          <span className="instrument-meta">Recherche sur l’ensemble de la base</span>
          <span className="instrument-cta">
            {active === null ? "Session en cours" : "Interroger partout →"}
          </span>
        </button>

        {rapports.map((r) => (
          <button
            key={r.stem}
            className={`instrument ${active === r.stem ? "active" : ""}`}
            onClick={() => onSelect(r.stem)}
          >
            <span className="instrument-name">{niceName(r.stem)}</span>
            <span className="instrument-meta">
              {r.pdf} · {r.pages} pages · {r.csv_rows} lignes · {r.chunks} extraits
            </span>
            <span className="instrument-cta">
              {active === r.stem ? "Session en cours" : "Interroger ce rapport →"}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}