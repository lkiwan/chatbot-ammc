/**
 * Prerenders the public routes to real HTML files in the build output.
 *
 * Why: the React app ships an empty <div id="root">, so Google's *ad* crawler
 * (AdsBot-Google / Mediapartners-Google), which does not reliably execute
 * JavaScript, lands on a blank page and the site looks empty during review.
 * Writing a sibling .html per route means each URL serves its text directly,
 * while the JS bundle still hydrates it into the full app on load.
 *
 * Content comes from the same JSON/bundle the React routes read, so the two
 * can't drift.
 *
 * Run after `vite build`:  node scripts/prerender.mjs
 */
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(join(fileURLToPath(import.meta.url), "..", ".."));
const dist = join(root, "frontend", "dist");

const SITE = JSON.parse(readFileSync(join(root, "frontend/src/content/site.json"), "utf8"));
const LEGAL = JSON.parse(readFileSync(join(root, "frontend/src/content/legal.json"), "utf8"));

const publicIndexSrc = readFileSync(join(root, "frontend/src/data/publicIndex.js"), "utf8");
const PUBLIC_INDEX = JSON.parse(
  publicIndexSrc.slice(publicIndexSrc.indexOf("{"), publicIndexSrc.lastIndexOf(";")).trim(),
);

const ORIGIN = "https://www.aivox.website";

// ── helpers ────────────────────────────────────────────────────────────────
const esc = (s) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const fill = (s) =>
  String(s || "").replace(/\{\{(\w+)\}\}/g, (m, k) =>
    Object.prototype.hasOwnProperty.call(SITE, k) ? String(SITE[k]) : m,
  );

const fillHtml = (s) => esc(fill(s));

function blocksHtml(blocks) {
  return blocks
    .map((b) => {
      if (b.type === "ul") {
        return `      <ul>\n${b.items.map((i) => `        <li>${fillHtml(i)}</li>`).join("\n")}\n      </ul>`;
      }
      if (b.type === "h2") return `      <h2>${fillHtml(b.text)}</h2>`;
      return `      <p>${fillHtml(b.text)}</p>`;
    })
    .join("\n");
}

function assetTag(rel, href) {
  if (rel === "icon") {
    // Keep the sizes attribute so the browser does not guess.
    const m = href.match(/^(.*\/)([^/]+)\.png$/);
    const size = m && m[2].replace(/\D/g, "");
    return size
      ? `    <link rel="icon" type="image/png" sizes="${size}" href="${href}" />`
      : `    <link rel="icon" href="${href}" />`;
  }
  if (rel === "apple-touch-icon") {
    const m = href.match(/^(.*\/)([^/]+)\.png$/);
    const size = m && m[2].replace(/\D/g, "");
    return `    <link rel="apple-touch-icon" sizes="${size}" href="${href}" />`;
  }
  if (rel === "stylesheet") return `    <link rel="stylesheet" crossorigin href="${href}" />`;
  return `    <link rel="${rel}" href="${href}" />`;
}

/**
 * Rebuilds a full document from the built index.html, swapping the body.
 *
 * The prerendered markup goes INSIDE #root. React mounts with createRoot(),
 * which clears the container before its first render, so crawlers read the
 * static text and a live browser replaces it with the real app. Emitting the
 * markup outside #root instead leaves createRoot(null), which silently kills
 * every interactive control on the page.
 */
function buildDoc({ title, description, bodyHtml, canonical, head, bodyClass, robots }) {
  return `<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>${esc(title)}</title>
    <meta name="description" content="${esc(description)}" />
    <link rel="canonical" href="${canonical}" />
${robots ? `    <meta name="robots" content="${robots}" />\n` : ""}${head}
  </head>
  <body${bodyClass ? ` class="${bodyClass}"` : ""}>
    <div id="root">
${bodyHtml}
    </div>
    <script type="module" src="/assets/entry.js"></script>
  </body>
</html>
`;
}

/**
 * The app shell: an empty #root for React to fill, no marketing content and no
 * indexable text. /app must NOT be served the landing prerender, otherwise
 * "Ouvrir l'application" appears to do nothing - the browser would just reload
 * the same marketing page.
 */
function buildAppShell() {
  return `<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>Connexion · ${esc(SITE.siteName)}</title>
    <meta name="description" content="Connexion à l'application ${esc(SITE.siteName)}." />
    <meta name="robots" content="noindex, nofollow" />
${head}
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/assets/entry.js"></script>
  </body>
</html>
`;
}

// ── read the built shell to reuse its head assets ───────────────────────────
const builtIndexPath = join(dist, "index.html");
if (!existsSync(builtIndexPath)) {
  console.error("dist/index.html not found - run `npm run build` first.");
  process.exit(1);
}
const built = readFileSync(builtIndexPath, "utf8");

// Extract asset references from the real build output.
const stylesheetHref = (built.match(/<link rel="stylesheet"[^>]*href="([^"]+)"/) || [])[1];
const moduleSrc = (built.match(/<script type="module"[^>]*src="([^"]+)"/) || [])[1];

const headAssets = [
  stylesheetHref ? assetTag("stylesheet", stylesheetHref) : null,
  '    <link rel="preconnect" href="https://fonts.googleapis.com" />',
  '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />',
  '    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />',
  '    <link rel="manifest" href="/site.webmanifest" />',
  '    <meta name="theme-color" content="#0b1424" />',
  '    <link rel="apple-touch-icon" sizes="180" href="/apple-touch-icon.png" />',
  '    <link rel="apple-touch-icon" sizes="192" href="/icon-192.png" />',
  '    <link rel="icon" type="image/png" sizes="32" href="/favicon-32.png" />',
  '    <link rel="icon" href="/logo.png" />',
  '    <meta name="google-adsense-account" content="ca-pub-7713392774673260" />',
  '    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7713392774673260" crossorigin="anonymous"></script>',
]
  .filter(Boolean)
  .join("\n");

// The bundle must be renamed to a stable path so every prerendered file
// points at the same entry. See renameEntry() at the bottom.
const head = headAssets;
const ENTRY = "/assets/entry.js";

// ── page shells ────────────────────────────────────────────────────────────
function shell({ title, description, canonical, inner, active }) {
  const navLink = (href, label, key) =>
    `<a href="${href}"${key === active ? ' aria-current="page"' : ""}>${esc(label)}</a>`;

  const nav = [
    navLink("/companies", "Sociétés", "companies"),
    navLink("/about", "À propos", "about"),
    navLink("/contact", "Contact", "contact"),
  ].join("\n            ");

  return `  <div class="pub">
    <header class="pub-nav">
      <a class="pub-brand" href="/">
        <img src="/logo.png" alt="" width="26" height="26" />
        <span>${esc(SITE.siteName)}</span>
      </a>
      <nav>
            ${nav}
      </nav>
    </header>
    <main class="pub-main">
${inner}
    </main>
    <footer class="pub-foot">
      <p>${esc(SITE.siteName)} — ${esc(SITE.tagline)}.</p>
      <p class="pub-foot-links">
        <a href="/privacy">Confidentialité</a> ·
        <a href="/terms">Conditions</a> ·
        <a href="/about">À propos</a> ·
        <a href="/contact">Contact</a> ·
        <a href="/app">Se connecter</a>
      </p>
    </footer>
  </div>`;
}

const footerLinks = `      <h2>Informations</h2>
      <ul class="pub-chips">
        <li><a href="/privacy">Politique de confidentialité</a></li>
        <li><a href="/terms">Conditions générales</a></li>
        <li><a href="/about">À propos</a></li>
        <li><a href="/contact">Contact</a></li>
      </ul>`;

// ── landing ────────────────────────────────────────────────────────────────
const T = PUBLIC_INDEX.totals;
const sectors = [...new Set(PUBLIC_INDEX.companies.map((c) => c.sector))].sort((a, b) => a.localeCompare(b, "fr"));

const landing = shell({
  active: "home",
  title: `${SITE.siteName} · ${SITE.tagline}`,
  description: `${SITE.siteName} analyse les rapports annuels des ${T.companies} sociétés cotées à la Bourse de Casablanca. ${T.reports} documents indexés, réponses sourcées page par page.`,
  canonical: `${ORIGIN}/`,
  inner: `      <section class="pub-hero">
        <img src="/logo.png" alt="${esc(SITE.siteName)}" class="pub-hero-logo" width="88" height="88" />
        <h1>${esc(SITE.siteName)}</h1>
        <p class="pub-hero-sub">Financial Intelligence · Bourse de Casablanca</p>
        <p class="pub-lede">Moteur d'analyse des rapports annuels des sociétés cotées à la Bourse de Casablanca. Chaque document est découpé en extraits indexés : posez une question en langage naturel et obtenez une réponse sourcée, avec la page exacte du rapport.</p>
        <ul class="pub-stats">
          <li><strong>${T.companies}</strong> sociétés</li>
          <li><strong>${T.reports}</strong> rapports</li>
          <li><strong>${T.chunks.toLocaleString("fr-FR").replace(/ | /g, " ")}</strong> extraits indexés</li>
          <li><strong>${T.sectors}</strong> secteurs</li>
        </ul>
        <div class="pub-cta">
          <a class="pub-cta-btn" href="/app">Ouvrir l'application</a>
        </div>
      </section>

      <section class="pub-features">
        <h2>Ce que fait ${esc(SITE.siteName)}</h2>
        <div class="pub-grid">
          <div>
            <h3>Analyse sourcée</h3>
            <p>Chaque réponse cite la société, le rapport et la page exacte d'où elle provient.</p>
          </div>
          <div>
            <h3>Couverture sectorielle</h3>
            <p>Banques, assurances, télécoms, énergie, immobilier, agroalimentaire, mines et plus encore.</p>
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

      <section class="pub-index">
        <h2>Index des ${T.companies} sociétés cotées</h2>
        <p>${T.reports} rapports annuels, ${T.pages.toLocaleString("fr-FR").replace(/ | /g, " ")} pages et ${T.chunks.toLocaleString("fr-FR").replace(/ | /g, " ")} excerpts indexés, classés par secteur.</p>
        <ul class="pub-chips">
${PUBLIC_INDEX.companies
  .slice(0, 60)
  .map((c) => `          <li><a href="/company/${c.slug}">${esc(c.company)}</a></li>`)
  .join("\n")}
        </ul>
        <p class="pub-more"><a href="/companies">Voir les ${T.companies} sociétés →</a></p>
      </section>

${footerLinks}`,
});

// ── companies index ────────────────────────────────────────────────────────
const bySector = {};
for (const c of PUBLIC_INDEX.companies) {
  (bySector[c.sector || "Non classé"] ||= []).push(c);
}
const sectorOrder = Object.keys(bySector).sort(
  (a, b) => bySector[b].length - bySector[a].length || a.localeCompare(b, "fr"),
);

const companiesPage = shell({
  active: "companies",
  title: `Sociétés cotées indexées | ${SITE.siteName}`,
  description: `Les ${T.companies} sociétés cotées à la Bourse de Casablanca dont les rapports annuels sont indexés sur ${SITE.siteName}, par secteur.`,
  canonical: `${ORIGIN}/companies`,
  inner: `      <h1>Sociétés cotées indexées</h1>
      <p class="pub-lede">${T.companies} sociétés cotées à la Bourse de Casablanca, réparties en ${sectorOrder.length} secteurs, pour ${T.reports} rapports annuels et ${T.chunks.toLocaleString("fr-FR").replace(/ | /g, " ")} excerpts indexés. Chaque entrée donne accès aux rapports correspondants.</p>
${sectorOrder
  .map(
    (s) => `      <section class="pub-sector">
        <h2>${esc(s)} <span class="pub-count">${bySector[s].length}</span></h2>
        <ul class="pub-list">
${bySector[s]
  .map(
    (c) =>
      `          <li><a href="/company/${c.slug}">${esc(c.company)}</a> <span class="pub-list-meta"><code>${esc(c.slug)}</code> ${c.years.length} rapport${c.years.length > 1 ? "s" : ""}</span></li>`,
  )
  .join("\n")}
        </ul>
      </section>`,
  )
  .join("\n")}

${footerLinks}`,
});

// ── company pages ──────────────────────────────────────────────────────────
function companyPage(c) {
  const years = c.years.join(", ");
  return shell({
    active: "companies",
    title: `${c.company} — rapports annuels | ${SITE.siteName}`,
    description: `Rapports annuels de ${c.company} (${c.sector || "Casablanca Stock Exchange"}) disponibles sur ${SITE.siteName} : ${years}.`,
    canonical: `${ORIGIN}/company/${c.slug}`,
    inner: `      <article class="pub-company">
        <h1>${esc(c.company)}</h1>
        <p class="pub-company-sub">${esc(c.sector || "Non classé")}</p>

        <h2>Rapports annuels disponibles</h2>
        <p>${SITE.siteName} indexe ${c.years.length} rapport${c.years.length > 1 ? "s" : ""} de ${esc(c.company)}, couvrant ${esc(years)}. Chaque document est découpé en extraits indexés, ce qui permet d'interroger les chiffres clés, les agrégats et le texte du rapport en langage naturel.</p>
        <ul class="pub-years">
${c.years.map((y) => `          <li>${esc(y)}</li>`).join("\n")}
        </ul>

        <h2>Exercices disponibles</h2>
        <ul>
${c.years.map((y) => `          <li><strong>${esc(y)}</strong> — rapport annuel et états financiers de ${esc(c.company)}</li>`).join("\n")}
        </ul>

        <h2>Ce que vous pouvez analyser</h2>
        <p>Chiffre d'affaires, résultat net, capacité d'autofinancement, dividendes, indicateurs de rentabilité et structure de l'actionnariat, à partir des comptes annuels publiés. L'outil répond par synthèse sourcée, chaque réponse renvoyant vers la page exacte du rapport.</p>

        <h2>À propos d'${esc(SITE.siteName)}</h2>
        <p>${esc(SITE.siteName)} est un moteur d'analyse des rapports annuels des sociétés cotées à la Bourse de Casablanca. L'index couvre ${T.reports} documents et ${T.companies} sociétés réparties en ${T.sectors} secteurs, découpés en ${T.chunks.toLocaleString("fr-FR").replace(/ | /g, " ")} excerpts indexés pour la recherche.</p>

        <div class="pub-cta">
          <a class="pub-cta-btn" href="/app">Ouvrir l'application</a>
        </div>

        <p class="pub-back"><a href="/companies">← Voir les ${T.companies} sociétés</a></p>
      </article>

${footerLinks}`,
  });
}

// ── legal pages ────────────────────────────────────────────────────────────
const LEGAL_ROUTES = {
  privacy: "/privacy",
  about: "/about",
  contact: "/contact",
  terms: "/conditions",
};

function legalPage(key) {
  const page = LEGAL[key];
  return shell({
    active: key,
    title: `${page.title} | ${SITE.siteName}`,
    description: page.description,
    canonical: `${ORIGIN}${LEGAL_ROUTES[key]}`,
    inner: `      <article class="pub-legal">
        <h1>${esc(page.title)}</h1>
        <p class="pub-legal-date">Mise à jour : ${esc(page.updated)}</p>
${blocksHtml(page.blocks)}

${footerLinks}
      </article>`,
  });
}

// ── write ──────────────────────────────────────────────────────────────────
let written = 0;

function writeRoute(routePath, { title, description, inner }) {
  const html = buildDoc({
    title,
    description,
    canonical: `${ORIGIN}${routePath}`,
    head,
    bodyClass: "pub-body",
    bodyHtml: inner,
  });
  const file = outFileFor(routePath);
  mkdirSync(join(file, ".."), { recursive: true });
  writeFileSync(file, html, "utf8");
  written++;
}

function outFileFor(routePath) {
  return routePath === "/"
    ? join(dist, "index.html")
    : join(dist, routePath.replace(/^\//, ""), "index.html");
}

writeRoute("/", {
  title: `${SITE.siteName} · ${SITE.tagline}`,
  description: landing.match(/<p class="pub-lede">([\s\S]*?)<\/p>/)[1],
  inner: landing,
});
writeRoute("/companies", {
  title: `Sociétés cotées indexées | ${SITE.siteName}`,
  description: companiesPage.match(/<p class="pub-lede">([\s\S]*?)<\/p>/)[1],
  inner: companiesPage,
});
for (const c of PUBLIC_INDEX.companies) {
  const inner = companyPage(c);
  writeRoute(`/company/${c.slug}`, {
    title: `${c.company} — rapports annuels | ${SITE.siteName}`,
    description: `Rapports annuels de ${c.company} (${c.sector || "Casablanca Stock Exchange"}) disponibles sur ${SITE.siteName} : ${c.years.join(", ")}.`,
    inner,
  });
}
for (const key of Object.keys(LEGAL_ROUTES)) {
  const page = LEGAL[key];
  writeRoute(LEGAL_ROUTES[key], {
    title: `${page.title} | ${SITE.siteName}`,
    description: page.description,
    inner: legalPage(key),
  });
}

// The private app gets a bare shell - see buildAppShell() for why it must not
// receive the landing prerender.
mkdirSync(join(dist, "app"), { recursive: true });
writeFileSync(join(dist, "app", "index.html"), buildAppShell(), "utf8");

/**
 * The prerendered documents all reference a stable /assets/entry.js. Copy the
 * real bundle under that name so the paths resolve, keeping the original too
 * for anything still pointing at the hashed name.
 */
function renameEntry() {
  const assets = join(dist, "assets");
  if (!existsSync(assets)) return;
  const hashed = readdirSync(assets).find((f) => /^index-.*\.js$/.test(f));
  if (hashed) {
    writeFileSync(join(assets, "entry.js"), readFileSync(join(assets, hashed)), "utf8");
  }
}
renameEntry();

console.log(`prerendered ${written} routes into ${dist}`);
console.log(`  1 landing, 1 companies, ${PUBLIC_INDEX.companies.length} company, ${Object.keys(LEGAL_ROUTES).length} legal`);
if (written !== 1 + 1 + PUBLIC_INDEX.companies.length + Object.keys(LEGAL_ROUTES).length) {
  process.exit(1);
}