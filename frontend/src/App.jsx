import React, { useEffect, useRef, useState } from "react";
import { fetchHealth, fetchMetrics, fetchReport } from "./api.js";
import Metrics from "./components/Metrics.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import DataExplorer from "./components/DataExplorer.jsx";
import About from "./components/About.jsx";

const SECTIONS = ["analyse", "donnees", "methode"];

export default function App() {
  const [report, setReport] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [apiUp, setApiUp] = useState(null);
  const [tab, setTab] = useState("analyse");
  const sectionRefs = useRef({});

  useEffect(() => {
    fetchHealth()
      .then((h) => setApiUp(h.index))
      .catch(() => setApiUp(false));
    fetchReport()
      .then(setReport)
      .catch(() => setReport(null));
    fetchMetrics()
      .then(setMetrics)
      .catch(() => setMetrics([]));
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            observer.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [tab]);

  const go = (section) => {
    setTab(section);
    const el = sectionRefs.current[section];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
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
          {report && <span className="edition">{report.titre}</span>}
          <span className={`api-state ${apiUp ? "up" : apiUp === null ? "pending" : "down"}`}>
            <span className="dot" />
            {apiUp ? "Index prêt" : apiUp === null ? "Connexion…" : "Hors ligne"}
          </span>
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">Semestre au 30 juin 2026 · Attijariwafa bank SA</p>
        <h1>
          Les résultats<br />
          <em>qu’on interroge.</em>
        </h1>
        <p className="hero-intro">
          Une interface pour lire, interroger et vérifier les états financiers publiés
          par la banque. Chaque réponse renvoie aux pages du rapport — rien n’est inventé,
          tout est sourcé.
        </p>
        <div className="hero-actions">
          <button className="btn btn-primary" onClick={() => go("analyse")}>
            Poser une question
          </button>
          <button className="btn btn-ghost" onClick={() => go("donnees")}>
            Explorer les tableaux
          </button>
        </div>
        {report && (
          <ul className="hero-facts">
            <li>{report.pages} pages analysées</li>
            <li>{report.chunks} extraits indexés</li>
            <li>{report.csv_rows} lignes structurées</li>
          </ul>
        )}
      </section>

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
            </div>
          </div>
          <ChatPanel />
        </section>

        <section
          id="donnees"
          className={`section reveal ${tab === "donnees" ? "visible" : ""}`}
          ref={(el) => (sectionRefs.current.donnees = el)}
        >
          <div className="section-head">
            <div>
              <p className="eyebrow">Extraction millimétrique</p>
              <h2>Les tableaux, tels qu’ils figurent au rapport.</h2>
            </div>
          </div>
          <DataExplorer />
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
            </div>
          </div>
          <About />
        </section>
      </main>

      <footer className="footer">
        <div className="wrap">
          <p>
            26 pages · 163 extraits indexés · 88 tableaux extraits · modèle{" "}
            <code>Atria-Dawn-Preview</code>
          </p>
          <p className="footer-note">
            Chiffres issus du rapport semestriel 2026 publié par Attijariwafa bank. Les
            réponses citent les pages du document.
          </p>
        </div>
      </footer>
    </div>
  );
}