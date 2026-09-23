"""
Populate companies and reports tables from the AMMC scraper manifest CSV.

Idempotent: uses ON CONFLICT DO NOTHING / upsert logic.
Run: python scripts/populate_db.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import SCRAPER_MANIFEST, SCRAPER_COMPANIES, PDFS_DIR
from db.models import Company, Report
from db.session import get_db, check_connection

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Convert company name to a stable ASCII slug."""
    nfd  = unicodedata.normalize("NFD", name)
    asc  = nfd.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", asc.lower()).strip("_")
    return slug


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def load_companies_csv() -> dict[str, dict]:
    """Load ammc companies.csv → {name: {sector, ammc_id, ammc_url}}."""
    if not SCRAPER_COMPANIES.exists():
        logger.warning("companies.csv not found at %s", SCRAPER_COMPANIES)
        return {}
    companies: dict[str, dict] = {}
    with open(SCRAPER_COMPANIES, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", row.get("company", "")).strip()
            if name:
                companies[name] = {
                    "sector":   row.get("sector", "").strip() or None,
                    "ammc_id":  row.get("id", row.get("ammc_id", "")).strip() or None,
                    "ammc_url": row.get("url", row.get("ammc_url", "")).strip() or None,
                }
    logger.info("Loaded %d companies from CSV", len(companies))
    return companies


def populate(dry_run: bool = False) -> None:
    if not check_connection():
        logger.error("Cannot connect to PostgreSQL — is docker-compose up?")
        sys.exit(1)

    if not SCRAPER_MANIFEST.exists():
        logger.error("Manifest not found: %s", SCRAPER_MANIFEST)
        sys.exit(1)

    companies_meta = load_companies_csv()

    # Read manifest rows
    rows: list[dict] = []
    with open(SCRAPER_MANIFEST, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    logger.info("Manifest has %d rows", len(rows))

    if dry_run:
        logger.info("[DRY RUN] Would insert/update up to %d rows", len(rows))
        for r in rows[:5]:
            logger.info("  Sample: %s", r)
        return

    company_cache: dict[str, int] = {}   # normalized_name → db id
    n_companies = 0
    n_reports   = 0
    n_skipped   = 0

    with get_db() as db:
        for row in rows:
            raw_name = row.get("company", row.get("name", "")).strip()
            if not raw_name:
                continue

            norm = normalize_name(raw_name)

            # ── Upsert company ────────────────────────────────────────────
            if norm not in company_cache:
                existing = db.query(Company).filter_by(normalized_name=norm).first()
                if existing:
                    company_cache[norm] = existing.id
                else:
                    meta = companies_meta.get(raw_name, {})
                    company = Company(
                        name             = raw_name,
                        normalized_name  = norm,
                        sector           = meta.get("sector"),
                        ammc_id          = meta.get("ammc_id"),
                        ammc_url         = meta.get("ammc_url"),
                        country          = "MA",
                    )
                    db.add(company)
                    db.flush()  # get id
                    company_cache[norm] = company.id
                    n_companies += 1
                    logger.debug("Added company: %s", raw_name)

            company_id = company_cache[norm]

            # ── Upsert report ─────────────────────────────────────────────
            year_str = row.get("year", "").strip()
            try:
                year = int(year_str)
            except ValueError:
                logger.warning("Invalid year '%s' for %s — skipping", year_str, raw_name)
                n_skipped += 1
                continue

            pdf_filename_scraped = row.get("filename", row.get("pdf_filename", "")).strip()
            # Canonical filename used after ingest_scraped.py copy
            canonical_filename   = f"{norm}_{year}.pdf"
            pdf_path_obj         = PDFS_DIR / canonical_filename
            source_url           = row.get("url", row.get("source_url", "")).strip() or None

            existing_report = (
                db.query(Report)
                .filter_by(company_id=company_id, year=year, report_type="annual")
                .first()
            )
            if existing_report:
                # Update path if file now exists
                if pdf_path_obj.exists() and not existing_report.pdf_path:
                    existing_report.pdf_path     = str(pdf_path_obj)
                    existing_report.pdf_filename  = canonical_filename
                    existing_report.file_hash     = file_hash(pdf_path_obj)
                    existing_report.file_size     = pdf_path_obj.stat().st_size
                n_skipped += 1
                continue

            report = Report(
                company_id        = company_id,
                year              = year,
                report_type       = "annual",
                pdf_filename      = canonical_filename if pdf_path_obj.exists() else pdf_filename_scraped,
                pdf_path          = str(pdf_path_obj) if pdf_path_obj.exists() else None,
                source_url        = source_url,
                file_hash         = file_hash(pdf_path_obj) if pdf_path_obj.exists() else None,
                file_size         = pdf_path_obj.stat().st_size if pdf_path_obj.exists() else None,
                extraction_status = "pending",
                chroma_stem       = f"{norm}_{year}",
            )
            db.add(report)
            n_reports += 1

    logger.info(
        "Done — new companies: %d, new reports: %d, skipped: %d",
        n_companies, n_reports, n_skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate DB from scraper manifest")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()
    populate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
