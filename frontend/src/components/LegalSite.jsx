import React, { useEffect } from "react";
import AdSlot, { AD_SLOTS } from "./AdSlot.jsx";
import SITE from "../content/site.json";
import LEGAL from "../content/legal.json";

/**
 * Static informational pages: privacy policy, about, contact, terms.
 *
 * These are required for an AdSense approval and for the site to look
 * legitimate to a human reviewer. Text lives in content/legal.json so the
 * same source drives both this route and the prerendered HTML written by
 * scripts/prerender.mjs - keeping the two in sync is the whole point of the
 * JSON file.
 */

export const LEGAL_PAGES = {
  privacy: { path: "/privacy", label: "Politique de confidentialité" },
  about: { path: "/about", label: "À propos" },
  contact: { path: "/contact", label: "Contact" },
  terms: { path: "/conditions", label: "Conditions" },
};

/** Substitutes {{token}} placeholders from site.json. */
export function fillTokens(text) {
  return String(text || "").replace(/\{\{(\w+)\}\}/g, (m, key) =>
    Object.prototype.hasOwnProperty.call(SITE, key) ? String(SITE[key]) : m,
  );
}

function useHead(title, description) {
  useEffect(() => {
    document.title = title;
    const el = document.querySelector('meta[name="description"]');
    if (el) el.setAttribute("content", description);
  }, [title, description]);
}

export default function LegalRoute({ pageKey }) {
  const page = LEGAL[pageKey];

  useHead(
    page ? `${page.title} | ${SITE.siteName}` : "Introuvable | " + SITE.siteName,
    page ? page.description : "Cette page n'existe pas.",
  );

  return (
    <div className="pub">
      <header className="pub-nav">
        <a className="pub-brand" href="/">
          <img src="/logo.png" alt="" width="26" height="26" />
          <span>{SITE.siteName}</span>
        </a>
        <nav>
          <a href="/companies">Sociétés</a>
          <a href="/about">À propos</a>
          <a href="/contact">Contact</a>
        </nav>
      </header>

      <main className="pub-main">
        {page ? (
          <article className="pub-legal">
            <h1>{page.title}</h1>
            <p className="pub-legal-date">Mise à jour : {page.updated}</p>
            {page.blocks.map((b, i) =>
              b.type === "ul" ? (
                <ul key={i}>
                  {b.items.map((it, j) => (
                    <li key={j}>{fillTokens(it)}</li>
                  ))}
                </ul>
              ) : b.type === "h2" ? (
                <h2 key={i}>{fillTokens(b.text)}</h2>
              ) : (
                <p key={i}>{fillTokens(b.text)}</p>
              ),
            )}
          </article>
        ) : (
          <article>
            <h1>Introuvable</h1>
            <p className="pub-lede">Cette page n'existe pas.</p>
            <p><a href="/">Retour à l'accueil →</a></p>
          </article>
        )}

        <h2>Informations</h2>
        <ul className="pub-chips">
          {Object.entries(LEGAL_PAGES).map(([k, p]) => (
            <li key={k}>
              <a href={p.path}>{p.label}</a>
            </li>
          ))}
        </ul>

        <AdSlot slot={AD_SLOTS.footer} format="horizontal" className="ad-slot-footer" />

        <footer className="pub-foot">
          <p>{SITE.siteName} — {SITE.tagline}.</p>
          <p className="pub-foot-links">
            <a href="/privacy">Confidentialité</a> ·{" "}
            <a href="/terms">Conditions</a> ·{" "}
            <a href="/about">À propos</a> ·{" "}
            <a href="/contact">Contact</a> ·{" "}
            <a href="/app">Se connecter</a>
          </p>
        </footer>
      </main>
    </div>
  );
}