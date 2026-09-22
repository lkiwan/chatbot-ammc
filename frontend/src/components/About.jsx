import React from "react";

const STEPS = [
  {
    n: "01",
    t: "Extraction",
    d: "Les 26 pages du rapport sont lues. Les tableaux sont repérés et restructurés en lignes typées, page par page (1 327 lignes au total)."
  },
  {
    n: "02",
    t: "Indexation",
    d: "Le texte est découpé en 163 extraits, chacun relié à sa page d'origine, et indexé en embeddings pour la recherche sémantique."
  },
  {
    n: "03",
    t: "Interrogation",
    d: "Chaque question interroge l'index, puis le modèle relit les extraits pertinents et rédige une réponse chiffrée, avec les pages citées."
  }
];

export default function About() {
  return (
    <div className="method">
      <div className="method-grid">
        {STEPS.map((s) => (
          <article className="step reveal" key={s.n}>
            <span className="step-n">{s.n}</span>
            <h3>{s.t}</h3>
            <p>{s.d}</p>
          </article>
        ))}
      </div>

      <div className="method-notes">
        <div>
          <h3>Les données structurées</h3>
          <p>
            Le fichier <code>donnees.csv</code> contient chaque cellule des tableaux du
            rapport (page, numéro de tableau, ligne, colonnes). C'est cette base qui
            alimente l'onglet « Données des états ».
          </p>
        </div>
        <div>
          <h3>En cas de panne du modèle</h3>
          <p>
            Si l'API de génération est indisponible, un moteur de repli renvoie
            directement les extraits les plus pertinents de l'index — la lecture du
            rapport reste possible hors ligne.
          </p>
        </div>
        <div>
          <h3>Pourquoi faire confiance</h3>
          <p>
            Chaque réponse affiche les pages du rapport utilisées. Les chiffres
            encadrés dans les états (résultats, bilans, actionnariat) sont transcrits
            sans reformulation.
          </p>
        </div>
      </div>
    </div>
  );
}