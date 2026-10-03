import React, { useEffect, useState } from "react";
import AdSlot, { AD_SLOTS } from "./AdSlot.jsx";
import { TICKERS, LOGO_URLS } from "../data/logos.js";
import { PUBLIC_INDEX } from "../data/publicIndex.js";
import LegalRoute, { LEGAL_PAGES } from "./LegalSite.jsx";
import SITE from "../content/site.json";

/**
 * Public, crawlable pages.
 *
 * These exist because the app itself sits behind a login: an ad-review
 * crawler only ever sees the login form, which reads as an empty site. These
 * routes give Google and anyone arriving from search real text (sector,
 * ticker, available years, report counts) without needing an account.
 *
 * Data comes from a build-time snapshot (data/publicIndex.js) rather than the
 * API. /api/companies and /api/reports sit behind the API token and the site
 * is currently served from a tunnel, so relying on them would leave these
 * pages blank whenever the backend is unreachable or unauthenticated - which
 * is exactly the case a crawler would hit.
 *
 * Routing is by pathname rather than a router library - there are only three
 * public routes and the app has no router installed.
 */

function slugify(name) {
  return String(name || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Synchronous by design. The snapshot is bundled, so there is no loading
 * state and the first paint already contains the indexable text.
 */
function usePublicData() {
  return {
    companies: PUBLIC_INDEX.companies,
    reports: PUBLIC_INDEX.totals,
    state: "ready",
  };
}

function head(title, description) {
  useEffect(() => {
    document.title = title;
    const set = (sel, attr, val) => {
      const el = document.querySelector(sel);
      if (el) el.setAttribute(attr, val);
    };
    set('meta[name="description"]', "content", description);
  }, [title, description]);
}

const SITE_URL = "https://www.aivox.website";

function tickerFor(name) {
  return TICKERS[name] || "";
}

// ── One company ────────────────────────────────────────────────────────────
function CompanyPage({ name }) {
  const { companies, reports } = usePublicData();

  const found =
    companies.find((c) => c.slug === name) ||
    companies.find((c) => c.company_normalized === name || slugify(c.company) === name);

  head(
    found ? `${found.company} — rapports annuels | AnnualEdge` : "AnnualEdge",
    found
      ? `Rapports annuels de ${found.company} (${found.sector || "Casablanca Stock Exchange"}) disponibles sur AnnualEdge : ${found.years.join(", ")}.`
      : "AnnualEdge — analyse des rapports annuels des sociétés cotées à la Casablanca Stock Exchange.",
  );

  if (!found) return <PublicShell><NotFound what={name} /></PublicShell>;

  const ticker = tickerFor(found.company);
  const logo = LOGO_URLS[found.company];
  const sector = found.sector || "Non classé";
  const years = found.years || [];

  return (
    <PublicShell>
      <article className="pub-company">
        {logo && <img className="pub-company-logo" src={logo} alt={found.company} width="64" height="64" />}

        <h1>{found.company}</h1>
        <p className="pub-company-sub">
          {sector}
          {ticker && <> · Ticker <strong>{ticker}</strong> sur la Bourse de Casablanca</>}
        </p>

        <h2>Rapports annuels disponibles</h2>
        <p>
          AnnualEdge indexe <strong>{years.length}</strong> rapport{years.length > 1 ? "s" : ""}
          {years.length > 1 ? "s" : ""} de {found.company}, couvrant {years.join(", ")}.
          Chaque document est découpé en extraits indexés, ce qui permet d'interroger
          les chiffres clés, les agrégats et le texte du rapport en langage
          naturel.
        </p>
        <ul className="pub-years">
          {years.map((y) => (
            <li key={y}>{y}</li>
          ))}
        </ul>

        <h2>Ce que vous pouvez analyser</h2>
        <p>
          Chiffre d'affaires, résultat net, capacité d'autofinancement, dividendes,
          indicateurs de rentabilité et structure de l'actionnariat, à partir des
          comptes annuels publiés. L'outil répond par synthèse sourcée, chaque
          réponse renvoyant vers la page exacte du rapport.
        </p>

        <h2>À propos d'AnnualEdge</h2>
        <p>
          AnnualEdge est un moteur d'analyse des rapports annuels des sociétés cotées
          à la Bourse de Casablanca. L'index couvre {reports.reports} documents et{" "}
          {companies.length} sociétés réparties en {reports.sectors} secteurs, découpés
          en {reports.chunks.toLocaleString("fr")} extraits indexés pour la recherche.
        </p>

        <div className="pub-cta">
          <a className="pub-cta-btn" href="/app">
            Ouvrir l'application
          </a>
        </div>

        <AdSlot slot={AD_SLOTS.footer} format="horizontal" className="ad-slot-footer" />
      </article>
    </PublicShell>
  );
}

// ── All companies ──────────────────────────────────────────────────────────
function CompaniesPage() {
  const { companies, reports } = usePublicData();

  head(
    "Sociétés cotées indexées | AnnualEdge",
    `Les ${companies.length} sociétés cotées à la Bourse de Casablanca dont les rapports annuels sont indexés sur AnnualEdge, par secteur.`,
  );

  const bySector = {};
  for (const c of companies) {
    const s = c.sector || "Non classé";
    (bySector[s] ||= []).push(c);
  }
  const sectors = Object.keys(bySector).sort((a, b) => bySector[b].length - bySector[a].length);

  return (
    <PublicShell>
      <h1>Sociétés cotées indexées</h1>
      <p className="pub-lede">
        {companies.length} sociétés cotées à la Bourse de Casablanca, réparties en{" "}
        {sectors.length} secteurs, pour {reports.reports} rapports annuels et{" "}
        {reports.chunks.toLocaleString("fr")} excerpts indexés. Chaque entrée donne
        accès aux rapports correspondants.
      </p>

      {sectors.map((s) => (
        <section key={s} className="pub-sector">
          <h2>{s} <span className="pub-count">{bySector[s].length}</span></h2>
          <ul className="pub-list">
            {bySector[s].map((c) => (
              <li key={c.company_normalized}>
                <a href={`/company/${slugify(c.company)}`}>{c.company}</a>
                <span className="pub-list-meta">
                  {tickerFor(c.company) && <code>{tickerFor(c.company)}</code>}
                  {c.years.length} rapport{c.years.length > 1 ? "s" : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <AdSlot slot={AD_SLOTS.footer} format="horizontal" className="ad-slot-footer" />
    </PublicShell>
  );
}

// ── Landing ────────────────────────────────────────────────────────────────
function LandingPage() {
  const { companies, reports } = usePublicData();

  head(
    "AnnualEdge — analyse des rapports annuels de la Bourse de Casablanca",
    `AnnualEdge analyse les rapports annuels des ${companies.length} sociétés cotées à la Bourse de Casablanca. ${reports.reports} documents indexés, réponses sourcées page par page.`,
  );

  return (
    <PublicShell>
      <section className="pub-hero">
        <img src="/logo.png" alt="AnnualEdge" className="pub-hero-logo" width="88" height="88" />
        <h1>AnnualEdge</h1>
        <p className="pub-hero-sub">Financial Intelligence · Bourse de Casablanca</p>
        <p className="pub-lede">
          Moteur d'analyse des rapports annuels des sociétés cotées à la Bourse de
          Casablanca. Chaque document est découpé en extraits indexés : posez une
          question en langage naturel et obtenez une réponse sourcée, avec la page
          exacte du rapport.
        </p>

        <ul className="pub-stats">
          <li><strong>{companies.length}</strong> sociétés</li>
          <li><strong>{reports.reports}</strong> rapports</li>
          <li><strong>{reports.chunks.toLocaleString("fr")}</strong> extraits indexés</li>
          <li><strong>{reports.sectors}</strong> secteurs</li>
        </ul>

        <div className="pub-cta">
          <a href="/app" className="pub-cta-btn">
            Ouvrir l'application
          </a>
        </div>
      </section>

      <AdSlot slot={AD_SLOTS.footer} format="horizontal" className="ad-slot-footer" />

      <section className="pub-features">
        <h2>Ce que fait AnnualEdge</h2>
        <div className="pub-grid">
          <div>
            <h3>Analyse sourcée</h3>
            <p>Chaque réponse cite la société, le rapport et la page exacte d'où elle provient.</p>
          </div>
          <div>
            <h3>Couverture sectorielle</h3>
            <p>Banques, assurances, télécoms, Energie, Immobilier, Agroalimentaire, Mines et plus encore.</p>
          </div>
          <div>
            <h3>Plusieurs exercices</h3>
            <p>Interrogez un même groupe sur plusieurs années pour suivre l'évolution de ses agrégats.</p>
          </div>
          <div>
            <h3>Visionneuse intégrée</h3>
            <p>La page source s'ouvre directement à côté de la conversation, sans quitter l'écran.</p>
          </div>
        </div>
      </section>

      <section className="pub-index">
        <h2>Index des sociétés</h2>
        <p>
          {companies.length} sociétés cotées, classées par secteur, avec leurs rapports
          annuels disponibles.
        </p>
        <ul className="pub-chips">
          {companies.slice(0, 60).map((c) => (
            <li key={c.company_normalized}>
              <a href={`/company/${slugify(c.company)}`}>{c.company}</a>
            </li>
          ))}
        </ul>
        {companies.length > 60 && (
          <p className="pub-more">
            <a href="/companies">Voir les {companies.length} sociétés →</a>
          </p>
        )}
      </section>
    </PublicShell>
  );
}

function NotFound({ what }) {
  return (
    <>
      <h1>Introuvable</h1>
      <p className="pub-lede">Aucune société ne correspond à « {what} ».</p>
      <p><a href="/companies">Parcourir l'index des sociétés →</a></p>
    </>
  );
}

function PublicShell({ children }) {
  return (
    <div className="pub">
      <header className="pub-nav">
        <a className="pub-brand" href="/">
          <img src="/logo.png" alt="" width="26" height="26" />
          <span>AnnualEdge</span>
        </a>
        <nav>
          <a href="/companies">Sociétés</a>
          <a href="/about">À propos</a>
          <a href="/contact">Contact</a>
        </nav>
      </header>
      <main className="pub-main">{children}</main>
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
    </div>
  );
}

/**
 * Resolves the current path to a public page. Returns null when the path is the
 * app itself, so the logged-in experience is untouched.
 */
export default function PublicRoute() {
  const [path, setPath] = useState(
    () => (typeof window === "undefined" ? "/" : window.location.pathname),
  );

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go = (to) => {
    window.history.pushState({}, "", to);
    setPath(to);
    window.scrollTo(0, 0);
  };

  const m = path.match(/^\/company\/([^/]+)\/?$/);
  if (m) return <CompanyPage name={decodeURIComponent(m[1])} />;
  if (/^\/companies\/?$/.test(path)) return <CompaniesPage />;
  if (/^\/?$/.test(path)) return <LandingPage />;
  if (/^\/app\/?$/.test(path)) {
    return null;
  }
  const legal = Object.keys(LEGAL_PAGES).find((k) => LEGAL_PAGES[k].path === path);
  if (legal) return <LegalRoute pageKey={legal} />;
  return (
    <PublicShell>
      <NotFound what={path} />
    </PublicShell>
  );
}