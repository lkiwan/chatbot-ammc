import React, { useEffect, useRef, useState } from "react";
import { fetchHealth, fetchMetrics, fetchReports } from "./api.js";
import Metrics from "./components/Metrics.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import DataExplorer from "./components/DataExplorer.jsx";
import ReportPicker from "./components/ReportPicker.jsx";
import About from "./components/About.jsx";

const QUICK_STEPS = [
  [
    "1",
    "Déposez un rapport",
    "Ajoutez un PDF de comptes dans data/pdfs/. Il est détecté, extrait et indexé automatiquement."
  ],
  [
    "2",
    "Sélectionnez-le",
    "Il apparaît dans « Instruments en base ». Un clic ouvre une session de questions dédiée."
  ],
  [
    "3",
    "Interrogez-le",
    "Posez votre question : la réponse cite le rapport et la page de chaque chiffre."
  ]
];

export default function App() {
  const [reports, setReports] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [apiUp, setApiUp] = useState(null);
  const [tab, setTab] = useState("analyse");
  const [activeRapport, setActiveRapport] = useState(null);
  const sectionRefs = useRef({});

  useEffect(() => {
    fetchHealth()
      .then((h) => setApiUp(h.index))
      .catch(() => setApiUp(false));
    fetchReports()
      .then(setReports)
      .catch(() => setReports(null));
    fetchMetrics()
      .then(setMetrics)
      .catch(() => setMetrics([]));
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      fetchReports().then(setReports).catch(() => {});
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  const total = reports?.total || null;

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    document.querySelectorAll(".reveal").forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight - 60) {
        el.classList.add("visible");
      } else {
        io.observe(el);
      }
    });
    return () => io.disconnect();
  }, [tab, reports, metrics]);

  const go = (section) => {
    setTab(section);
    const el = sectionRefs.current[section];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const selectRapport = (stem) => {
    setActiveRapport(stem);
    go("analyse");
  };

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">A</span>
          <span className="brand-name">AMMC</span>
          <span className="brand-sub">Publications financières</span>
        </div>
        <div className="topbar-meta">
          {total && (
            <span className="edition">
              {total.rapports} rapport{total.rapports > 1 ? "s" : ""} en base
            </span>
          )}
          <span className={`api-state ${apiUp ? "up" : apiUp === null ? "pending" : "down"}`}>
            <span className="dot" />
            {apiUp ? "Index prêt" : apiUp === null ? "Connexion…" : "Hors ligne"}
          </span>
        </div>
      </header>

      <section className="hero wrap">
        <div className="hero-text">
          <p className="eyebrow">Publications financières · arrêtés 2025–2026</p>
          <h1>
            Lisez, interrogez, <em>vérifiez.</em>
          </h1>
          <p className="hero-intro">
            Chaque rapport déposé dans <code>data/pdfs/</code> est lu automatiquement.
            Posez une question : la réponse est chiffrée et renvoie aux pages du document.
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={() => go("analyse")}>
              Poser une question
            </button>
            <button className="btn btn-ghost" onClick={() => go("donnees")}>
              Voir les tableaux
            </button>
          </div>
          {total && (
            <ul className="hero-facts">
              <li>{total.rapports} instrument{total.rapports > 1 ? "s" : ""}</li>
              <li>{total.pages} pages analysées</li>
              <li>{total.chunks} extraits indexés</li>
              <li>{total.csv_rows} lignes structurées</li>
            </ul>
          )}
        </div>

        <ol className="hero-steps">
          {QUICK_STEPS.map(([n, t, d]) => (
            <li key={n} className="step-card reveal">
              <span className="step-n">{n}</span>
              <p className="step-t">{t}</p>
              <p className="step-d">{d}</p>
            </li>
          ))}
        </ol>
      </section>

      {reports && (
        <ReportPicker
          rapports={reports.rapports}
          active={activeRapport}
          onSelect={selectRapport}
          total={reports.total}
        />
      )}

      {metrics.length > 0 && (
        <section className="metrics wrap reveal" ref={(el) => (sectionRefs.current.chiffres = el)}>
          <Metrics items={metrics} />
        </section>
      )}

      <nav className="tabs wrap">
        {[
          ["analyse", "Questions & analyse"],
          ["donnees", "Données des états"],
          ["methode", "La méthode"]
        ].map(([id, label]) => (
          <button
            key={id}
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => go(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="wrap">
        <section
          id="analyse"
          className={`section reveal ${tab === "analyse" ? "visible" : ""}`}
          ref={(el) => (sectionRefs.current.analyse = el)}
        >
          <div className="section-head">
            <div>
              <p className="eyebrow">Partie conversationnelle</p>
              <h2>Un analyste qui répond avec les chiffres.</h2>
              <p className="section-sub">
                Une question, une réponse sourcée. Chaque réponse affiche le rapport et
                la page des chiffres utilisés.
              </p>
            </div>
          </div>
          <ChatPanel key={activeRapport ?? "all"} rapport={activeRapport} />
        </section>

        <section
          id="donnees"
          className={`section reveal ${tab === "donnees" ? "visible" : ""}`}
          ref={(el) => (sectionRefs.current.donnees = el)}
        >
          <div className="section-head">
            <div>
              <p className="eyebrow">Extraction</p>
              <h2>Les tableaux, tels qu’ils figurent au rapport.</h2>
              <p className="section-sub">
                Filtrez par rapport ou par page, ou cherchez un mot dans les cellules.
              </p>
            </div>
          </div>
          <DataExplorer
            reportsCount={total?.rapports ?? 0}
            onRefresh={() => fetchReports().then(setReports)}
          />
        </section>

        <section
          id="methode"
          className={`section reveal ${tab === "methode" ? "visible" : ""}`}
          ref={(el) => (sectionRefs.current.methode = el)}
        >
          <div className="section-head">
            <div>
              <p className="eyebrow">Documentation</p>
              <h2>Comment les données sont préparées.</h2>
              <p className="section-sub">
                Extraction, indexation, interrogation : le chemin parcouru par chaque
                rapport.
              </p>
            </div>
          </div>
          <About />
        </section>
      </main>

      <footer className="footer">
        <div className="wrap">
          <p>
            {total
              ? `${total.pages} pages · ${total.chunks} extraits indexés · ${total.csv_rows} lignes structurées · ${total.rapports} rapport${total.rapports > 1 ? "s" : ""}`
              : "Chargement…"}{" "}
            · modèle <code>Atria-Dawn-Preview</code>
          </p>
          <p className="footer-note">
            Chiffres issus des rapports déposés dans <code>data/pdfs/</code>. Les
            réponses citent le rapport et les pages du document.
          </p>
        </div>
      </footer>
    </div>
  );
}