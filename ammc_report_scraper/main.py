"""
AMMC Annual Report Scraper - Main entry point.

Usage:
    python main.py
    python main.py --dry-run
    python main.py --sector "Banques"
    python main.py --company "ATTIJARIWAFA BANK"
    python main.py --year 2024
    python main.py --company "ATTIJARIWAFA BANK" --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make src importable
sys.path.insert(0, str(Path(__file__).parent))

from src.config import PATHS, SCRAPER
from src.downloaders.pdf_downloader import PDFDownloader
from src.parsers.report_parser import DownloadStatus, ReportRecord
from src.scrapers.ammc_company import AMMCCompanyScraper
from src.scrapers.ammc_emitters import AMMCEmitterScraper
from src.scrapers.ammc_reports import AMMCReportScraper
from src.scrapers.base import BaseSession
from src.storage.filesystem import ensure_project_dirs
from src.storage.manifest import ManifestManager
from src.utils.logger import get_logger

logger = get_logger("ammc_scraper", PATHS.logs_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AMMC Annual Report Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="List reports without downloading PDFs")
    parser.add_argument("--sector", type=str, default=None, help='Filter by sector, e.g. "Banques"')
    parser.add_argument("--company", type=str, default=None, help='Filter by company name, e.g. "ATTIJARIWAFA BANK"')
    parser.add_argument("--year", type=int, default=None, help="Filter: only include reports from this year")
    parser.add_argument("--max-reports", type=int, default=SCRAPER.max_years, help="Max reports per company (default: 5)")
    return parser.parse_args()


def print_banner(args: argparse.Namespace) -> None:
    logger.info("=" * 50)
    logger.info("AMMC ANNUAL REPORT SCRAPER")
    logger.info("=" * 50)
    if args.dry_run:
        logger.info("MODE: DRY RUN (no PDFs will be downloaded)")
    if args.sector:
        logger.info("FILTER sector: %s", args.sector)
    if args.company:
        logger.info("FILTER company: %s", args.company)
    if args.year:
        logger.info("FILTER year: %d", args.year)
    logger.info("Max reports per company: %d", args.max_reports)
    logger.info("=" * 50)


def print_dry_run_results(company_reports: dict[str, list[ReportRecord]]) -> None:
    print("\n" + "=" * 60)
    print("DRY RUN RESULTS")
    print("=" * 60)
    for company_name, reports in company_reports.items():
        if not reports:
            continue
        sector = reports[0].sector if reports else "?"
        print(f"\n{company_name}")
        print(f"  Sector: {sector}")
        print(f"  Selected reports:")
        for r in sorted(reports, key=lambda x: x.year, reverse=True):
            print(f"    {r.year}  -->  {r.source_url}")
    print("=" * 60 + "\n")


def print_summary(
    n_companies: int,
    n_processed: int,
    n_reports_found: int,
    n_selected: int,
    n_downloaded: int,
    n_skipped: int,
    n_failed: int,
) -> None:
    print("\n" + "=" * 50)
    print("AMMC SCRAPING SUMMARY")
    print("=" * 50)
    print(f"Companies found:      {n_companies}")
    print(f"Companies processed:  {n_processed}")
    print(f"Reports found:        {n_reports_found}")
    print(f"Reports selected:     {n_selected}")
    print(f"Downloaded:           {n_downloaded}")
    print(f"Already existing:     {n_skipped}")
    print(f"Failed:               {n_failed}")
    print("=" * 50 + "\n")


def main() -> None:
    args = parse_args()
    ensure_project_dirs()
    print_banner(args)

    session = BaseSession()
    manifest = ManifestManager()

    # ── Phase 1: Scrape emitters list ────────────────────────────────────────
    logger.info("Phase 1: Scraping AMMC emitters list")
    emitter_scraper = AMMCEmitterScraper(session=session)
    emitters = emitter_scraper.scrape_all(
        sector_filter=args.sector,
        company_filter=args.company,
    )

    if not emitters:
        logger.error("No companies found. Check network connection and AMMC site availability.")
        sys.exit(1)

    logger.info("Found %d companies", len(emitters))

    # Save companies.csv
    manifest.save_companies(emitters)
    logger.info("Saved companies.csv")

    # ── Phase 2: For each company, get annual reports ─────────────────────────
    logger.info("Phase 2: Fetching annual reports for each company")

    company_scraper = AMMCCompanyScraper(session=session)
    report_scraper = AMMCReportScraper(session=session)
    downloader = PDFDownloader(session=session)

    dry_run_map: dict[str, list[ReportRecord]] = {}

    n_reports_found_total = 0
    n_companies_processed = 0
    n_selected_total = 0
    n_downloaded = 0
    n_skipped = 0
    n_failed = 0

    for emitter in emitters:
        logger.info("Processing: %s [%s]", emitter.company_name, emitter.sector)

        # Get all annual reports for this company
        annual_reports = company_scraper.get_annual_reports(emitter)
        n_reports_found_total += len(annual_reports)

        if not annual_reports:
            logger.warning("No annual reports found for %s", emitter.company_name)
            n_companies_processed += 1
            continue

        # Filter by year if requested
        if args.year:
            annual_reports = [r for r in annual_reports if r.year == args.year]

        # Sort by year descending, deduplicate, select top N
        annual_reports.sort(key=lambda r: r.year, reverse=True)
        seen_years: set[int] = set()
        deduped: list[ReportRecord] = []
        for r in annual_reports:
            if r.year not in seen_years:
                seen_years.add(r.year)
                deduped.append(r)

        selected = deduped[: args.max_reports]
        n_selected_total += len(selected)
        logger.info(
            "%s: %d annual reports found, selected years: %s",
            emitter.company_name,
            len(deduped),
            ", ".join(str(r.year) for r in selected),
        )

        if args.dry_run:
            dry_run_map[emitter.company_name] = selected
            n_companies_processed += 1
            continue

        # ── Phase 3 + 4: Resolve PDF URL, download, validate ─────────────────
        for report in selected:
            # Skip if already successfully downloaded and valid
            if manifest.is_already_downloaded(report.report_id):
                logger.info("Already in manifest: %s %s - SKIP", report.company_name, report.year)
                n_skipped += 1
                continue

            # Resolve PDF URL from document page
            pdf_url = report_scraper.resolve_pdf_url(report)
            if not pdf_url:
                report.download_status = DownloadStatus.FAILED
                report.error = "Could not resolve PDF URL from document page"
                manifest.upsert_report(report)
                n_failed += 1
                continue

            report.document_url = pdf_url

            # Download + validate
            downloader.download(report, dry_run=False)
            manifest.upsert_report(report)

            if report.download_status == DownloadStatus.DOWNLOADED:
                n_downloaded += 1
            else:
                n_failed += 1

        n_companies_processed += 1

    # ── Dry run output ────────────────────────────────────────────────────────
    if args.dry_run:
        print_dry_run_results(dry_run_map)

    # ── Final summary ─────────────────────────────────────────────────────────
    print_summary(
        n_companies=len(emitters),
        n_processed=n_companies_processed,
        n_reports_found=n_reports_found_total,
        n_selected=n_selected_total,
        n_downloaded=n_downloaded,
        n_skipped=n_skipped,
        n_failed=n_failed,
    )


if __name__ == "__main__":
    main()
