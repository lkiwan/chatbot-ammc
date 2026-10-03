/**
 * Generates frontend/src/data/publicIndex.js from the scraped metadata and the
 * report registry.
 *
 * Why this exists: the public pages must render for search crawlers and the ad
 * reviewer, but /api/companies and /api/reports sit behind the API token. A
 * build-time snapshot keeps those pages readable without exposing a token or
 * depending on a tunnel being up.
 *
 * Run from the repo root:  node scripts/generate-public-index.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const meta = JSON.parse(readFileSync(resolve(root, "data/scraper_meta.json"), "utf8"));
const registry = JSON.parse(readFileSync(resolve(root, "data/reports.json"), "utf8"));

const indexed = new Set(registry.map((r) => r.stem));

/** Mirrors the slugify() used by the public pages and the API. */
function slugify(name) {
  return String(name || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const seen = new Map();
for (const [stem, m] of Object.entries(meta)) {
  if (!indexed.has(stem)) continue;
  const key = m.company_normalized || stem;
  if (!seen.has(key)) {
    seen.set(key, {
      slug: slugify(m.company || key),
      company: m.company || key,
      company_normalized: key,
      sector: m.sector || "",
      years: [],
    });
  }
  const year = m.year || "";
  if (year && !seen.get(key).years.includes(year)) seen.get(key).years.push(year);
}

const companies = [...seen.values()]
  .map((c) => ({ ...c, years: c.years.sort((a, b) => Number(b) - Number(a)) }))
  .sort((a, b) => a.company.localeCompare(b.company, "fr"));

const sectors = {};
for (const c of companies) {
  const s = c.sector || "Non classé";
  (sectors[s] ||= []).push(c.slug);
}

const totals = registry.reduce(
  (acc, r) => ({
    reports: acc.reports + 1,
    chunks: acc.chunks + (Number(r.chunks) || 0),
    pages: acc.pages + (Number(r.pages) || 0),
  }),
  { reports: 0, chunks: 0, pages: 0 },
);

const payload = {
  generated: new Date().toISOString().slice(0, 10),
  totals: { ...totals, companies: companies.length, sectors: Object.keys(sectors).length },
  companies,
};

/**
 * Sitemap is generated too: a static sitemap listing only "/" tells crawlers the
 * site is one page, which is the opposite of what we want to signal.
 */
// Written whole rather than patched, so re-running is idempotent.
const url = (loc, changefreq, priority) =>
  `  <url>\n    <loc>${loc}</loc>\n    <changefreq>${changefreq}</changefreq>\n` +
  `    <priority>${priority}</priority>\n  </url>`;

const sitemap = [
  `<?xml version="1.0" encoding="UTF-8"?>`,
  `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">`,
  url("https://www.aivox.website/", "weekly", "1.0"),
  url("https://www.aivox.website/companies", "weekly", "0.8"),
  ...companies.map((c) => url(`https://www.aivox.website/company/${c.slug}`, "monthly", "0.6")),
  `</urlset>`,
].join("\n");

writeFileSync(resolve(root, "frontend/public/sitemap.xml"), sitemap, "utf8");
console.log(`sitemap.xml: ${companies.length + 2} URLs`);

const body = `// GENERATED FILE - do not edit by hand.
// Source: data/scraper_meta.json + data/reports.json
// Regenerate: node scripts/generate-public-index.mjs
//
// Snapshot used by the public pages so they render without the API token.
export const PUBLIC_INDEX = ${JSON.stringify(payload)};
`;

writeFileSync(resolve(root, "frontend/src/data/publicIndex.js"), body, "utf8");
console.log(
  `publicIndex.js: ${companies.length} companies, ${totals.reports} reports, ` +
    `${totals.chunks} chunks, ${Object.keys(sectors).length} sectors`,
);