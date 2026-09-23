# AMMC Annual Report Scraper

Scrapes the 5 most recent annual reports for every company listed on the AMMC (Autorité Marocaine du Marché des Capitaux) website.

## Architecture

```
ammc_report_scraper/
├── src/
│   ├── scrapers/
│   │   ├── ammc_emitters.py   # Scrapes emitters list (all companies + sectors)
│   │   ├── ammc_company.py    # Scrapes individual company pages for report links
│   │   └── ammc_reports.py    # Scrapes document pages to extract PDF URLs
│   ├── downloaders/
│   │   └── pdf_downloader.py  # Downloads + validates PDFs (SHA256, PyMuPDF)
│   ├── parsers/
│   │   ├── emitter_parser.py  # Pydantic models for companies
│   │   └── report_parser.py   # Pydantic models for reports + detection logic
│   ├── storage/
│   │   ├── filesystem.py      # Directory management
│   │   └── manifest.py        # CSV manifest read/write
│   ├── utils/
│   │   ├── logger.py          # Structured logging
│   │   ├── hashing.py         # SHA-256 helpers
│   │   ├── normalization.py   # Company/sector name normalization
│   │   └── retry.py           # tenacity retry decorator
│   └── config.py              # Config loader from settings.yaml
├── data/
│   ├── companies/companies.csv
│   ├── reports/{Sector}/{Company}/{Year}/annual_report.pdf
│   └── manifests/reports_manifest.csv
├── logs/scraper.log
├── tests/
├── config/settings.yaml
├── main.py
└── requirements.txt
```

## Data Flow

```
AMMC emitters list (14 pages)
  ↓
Company list with IDs, names, sectors
  ↓
For each company: fetch emitter page /fr/espace-emetteurs/liste-des-emetteurs/{id}
  ↓
Extract all annual report links (/etats-financiers/{slug}-rfa-{year})
  ↓
Sort by year, select 5 most recent
  ↓
Fetch each document page → extract PDF URL
  ↓
Download PDF → validate → SHA-256 → store
  ↓
Update manifest CSV
```

## Installation

```bash
cd ammc_report_scraper
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

### Full scrape (all companies, all sectors)

```bash
python main.py
```

### Dry run (list reports without downloading)

```bash
python main.py --dry-run
```

### Filter by sector

```bash
python main.py --sector "Banques"
```

### Filter by company

```bash
python main.py --company "ATTIJARIWAFA BANK"
```

### Filter by year

```bash
python main.py --year 2025
```

### Combined filters

```bash
python main.py --company "ATTIJARIWAFA BANK" --dry-run
python main.py --sector "Banques" --year 2024
```

## Configuration

Edit `config/settings.yaml` to adjust:

- `scraper.delay`: seconds between requests (default: 1.5)
- `scraper.timeout`: HTTP timeout in seconds (default: 30)
- `scraper.max_retries`: retry attempts on failure (default: 3)
- `scraper.max_years`: max reports per company (default: 5)

## Output

### data/companies/companies.csv

| company_id | company_name | sector | ammc_url | ... |
|---|---|---|---|---|

### data/reports/{Sector}/{Company}/{Year}/annual_report.pdf

### data/manifests/reports_manifest.csv

| report_id | company_id | company_name | sector | year | download_status | sha256 | pdf_pages | ... |
|---|---|---|---|---|---|---|---|---|

### logs/scraper.log

```
2026-09-23 01:00:00 INFO     Starting AMMC scraper
2026-09-23 01:00:03 INFO     Found 196 companies
2026-09-23 01:00:04 INFO     Processing ATTIJARIWAFA BANK [Banques]
2026-09-23 01:00:05 INFO     ATTIJARIWAFA BANK: 7 annual reports found, selected: 2025, 2024, 2023, 2022, 2021
```

## Tests

```bash
pytest tests/ -v
pytest tests/ --cov=src
```

## Resuming after interruption

Re-run `python main.py`. The manifest tracks completed downloads; already-downloaded valid PDFs are skipped. Incomplete/invalid PDFs are automatically re-downloaded.

## Notes

- The scraper is polite: default 1.5 second delay between requests
- PDFs are validated with PyMuPDF before being marked as downloaded
- SHA-256 hashes enable deduplication
- Company name normalization handles `ATTIJARIWAFA BANK` / `Attijariwafa-bank` / `Attijariwafa Bank` as the same entity
