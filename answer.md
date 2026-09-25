# JSON Data Inventory — chatbot-ammc

Project: `C:\Users\walid\OneDrive\Bureau\chatbot-ammc`
Method: read-only inspection. Nothing modified, moved, deleted, zipped or uploaded. No database access.

---

## 1. Directories containing .json files

| Directory | Files | Size on disk |
|---|---:|---:|
| `data\chunks\` | 696 | 242.65 MB |
| `data\` | 4 | 0.33 MB |
| `frontend\` | 2 | 0.11 MB |
| `.claude\` | 1 | 0.01 MB |
| `ammc_report_scraper\data\` | **0** | — |
| `extraction\` | **0** | — |
| `db\` | **0** | — |
| `retrieval\`, `api\`, `scripts\` | **0** | — |

**Project JSON total (excl. `node_modules`): 703 files, 243.10 MB.**
With `node_modules` (189 npm package files, no project data): 892 files, 243.70 MB.

`ammc_report_scraper\data\` holds **609 PDFs + 2 CSVs, zero JSON** — the scraper manifest
`reports_manifest.csv` is 330,633 bytes of CSV, not JSON. `extraction\`, `db\`, `retrieval\`,
`api\` and `scripts\` contain no JSON at all; their data lives in `.py` files and the empty
PostgreSQL database.

### The four files in `data\`

```
   2,852 B  2026-09-25 17:51  analytics.json
     103 B  2026-09-25 17:27  analytics_geo.json
 120,002 B  2026-09-24 01:32  reports.json
 223,554 B  2026-09-23 21:08  scraper_meta.json
```

---

## 2. Structure per family

### Family A — index registry · `data/reports.json`
Array, **670 elements**.
Keys: `stem, pdf, pages, csv_rows, chunks, added, indexed`

```json
{ "stem": "cartier_saada_2019", "pdf": "annual_report.pdf", "pages": 113,
  "csv_rows": 2327, "chunks": 207, "added": null, "indexed": true }
{ "stem": "cartier_saada_2020", "pdf": "annual_report.pdf", "pages": 146,
  "csv_rows": 1939, "chunks": 318, "added": null, "indexed": true }
```

### Family B — scraper metadata · `data/scraper_meta.json`
Object keyed by stem, **609 keys**.
Keys per value: `company, company_normalized, year, sector, report_id, source_url, document_url`

```json
"attijariwafa_2025": {
  "company": "ATTIJARIWAFA BANK",
  "company_normalized": "attijariwafa",
  "year": "2025",
  "sector": "Banques",
  "report_id": "2734_2025",
  "source_url": "https://www.ammc.ma/fr/espace-emetteurs/etats-financiers/attijariwafa-bank-rfa-2025",
  "document_url": "https://www.ammc.ma/sites/default/files/AWB_RFA_2025.pdf"
}
```

### Family C — text chunks (the 161,252 excerpts) · `data/chunks\*.json`
Array. **687 of 696 files share one shape; 9 are empty arrays.**
Keys: `id, page, report, text, source`

```json
{ "id": 0, "page": 2, "report": "ctm_2023",
  "text": "ERIAMMOS 1/ Pr�sentation G�n�rale CTM EN BREF DATES CL�S CHIFFRES CL�S IMPLANTATIONS ACTIONNARIAT 2/...[+640 chars]",
  "source": "ctm_2023.pdf" }
{ "id": 1, "page": 3, "report": "ctm_2023",
  "text": "3202 leunnA reicnaniF troppaR - MTC ...[+122 chars]",
  "source": "ctm_2023.pdf" }
```

### Family D — analytics store · `data/analytics.json`
Object, **4 keys**: `visits, demo_logins, demo_messages, demo_exhausted`.
Keys per event: `ts, device, role?, ip, ip_hash, city, country, country_code, isp`

```json
{ "visits": [
    { "ts": "2026-09-25T17:23:43.942754+00:00",
      "device": "desktop",
      "ip": "127.0.0.1",
      "ip_hash": "230effc3088d",
      "city": "Local",
      "country": "Private Network",
      "country_code": "",
      "isp": "" }
  ],
  "demo_logins": [], "demo_messages": [], "demo_exhausted": [] }
```

### Family E — geo cache · `data\analytics_geo.json`
Object keyed by IP address.

```json
{ "8.8.8.8": { "city": "Ashburn",
               "country": "United States",
               "country_code": "US",
               "isp": "Google LLC" } }
```

### Family F — toolchain config (not project data)

| File | Size | Purpose |
|---|---:|---|
| `frontend\package.json` | 441 B | npm manifest |
| `frontend\package-lock.json` | 117,597 B | dependency lock |
| `.claude\settings.local.json` | 11,285 B | tool permissions |

---

## 3. Companies and years

**102 unique companies** in `scraper_meta.json` (keyed by `company_normalized`).
The UI displays **80** because `api/main.py:420-424` filters to stems present in
`reports.json` first — 198 registry stems have no metadata at all.

**Years 2019–2026**, across all 670 reports:

| Year | Reports |  | Year | Reports |
|---|---:|---|---|---:|
| 2019 | 73 |  | 2023 | 100 |
| 2020 | 99 |  | 2024 | 100 |
| 2021 | 96 |  | 2025 | 102 |
| 2022 | 99 |  | 2026 | 1 |

Every stem matches `_\d{4}$`; no malformed names.

**18 sectors:** Agro alimentaire, Assurances et Courtage, Autres, Banques, Carton emballage
impression, Chimie parachimie, Commerce et transport, Holding, Industrie métallurgique,
Industrie électrique, Matériaux de construction, Mines, Pharmaceutique, Pétrole-gaz et
lubrifiants, Sociétés de Financement, Sociétés de participations, Sociétés immobilières et
hôtelières, Télécommunications et nouvelles technologies.

---

## 4. Field presence across all 703 files

| Field | As JSON key | As text value | Where |
|---|---|---|---|
| `revenue` | no | **YES** | chunk prose only |
| `net_income` | no | no | — |
| `total_assets` | no | no | — |
| `ebitda` | no | **YES** | chunk prose only |
| `shareholder_name` | no | no | — |
| `ownership_percentage` | no | no | — |
| `ratio_name` | no | no | — |
| `section_name` | no | no | — |
| `company` | **YES** | **YES** | `scraper_meta.json` |
| `ticker` | no | **YES** | chunk prose only |
| `year` | **YES** | **YES** | `scraper_meta.json` |
| `chroma_stem` | no | no | — |
| `text` | **YES** | **YES** | `data/chunks/` |
| `page` | **YES** | **YES** | `data/chunks/` |
| `source` | **YES** | **YES** | `data/chunks/` |

**Critical finding:** the eight financial/relational fields `revenue`, `ebitda`, `ticker`
appear **only as prose inside extracted PDF text** — never as structured keys. The structured
counterparts the `db/models.py` schema expects (`net_income`, `total_assets`,
`shareholder_name`, `ownership_percentage`, `ratio_name`, `section_name`) appear **nowhere at
all**. The JSON on disk holds no queryable financial data: it is document text plus indexing
metadata. Any structured figures exist only inside `data/raw/*.csv` (696 files, 505,147 rows)
and the empty PostgreSQL database.

---

## 5. Total size

| Scope | Size |
|---|---:|
| **All project JSON (703 files, excl. node_modules)** | **243.10 MB** |
| — `data\chunks\` (696 files) | 242.65 MB |
| — `data\` (4 files) | 0.33 MB |
| — `frontend\` (2 files) | 0.11 MB |
| — `.claude\` (1 file) | 0.01 MB |
| With `node_modules` (892 files) | 243.70 MB |

`data\chunks\` alone is **99.8%** of all JSON: 696 files, min 2 B, max 2,159,517 B,
avg 365,568 B.

---

## Data-quality notes

- **9 empty chunk files** produce 0 excerpts: `cih_2022`, `cih_bank_2022`,
  `dari_couspate_2021`, `dari_couspate_2024`, `dari_couspate_2025` and 4 others. They are
  still counted as "indexed" reports.
- **26 orphan chunk files** are absent from `reports.json` (`credit_agricole_du_cam_2019`…) —
  stale artifacts, which is why 696 chunk files back only 670 reports.
- **Encoding is corrupted** in chunk text: `Pr�sentation G�n�rale`, `Industrie
  m�tallurgique`. These are CP1252/Latin-1 bytes stored as UTF-8, so accented French text is
  systematically mangled.
- `data\analytics.json` and `data\analytics_geo.json` are runtime artifacts regenerated on
  every page load. They hold raw IP addresses and are not project data.
