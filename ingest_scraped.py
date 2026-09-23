"""
Bridge script: indexes all PDFs scraped by ammc_report_scraper directly in
place (no copy to data/pdfs/). Generates data/scraper_meta.json and
reports.json, then builds (or updates) the ChromaDB index reading from
ammc_report_scraper/data/reports.

Usage:
    python ingest_scraped.py           # only new PDFs
    python ingest_scraped.py --force   # reindex everything from scratch
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "ammc_report_scraper" / "data" / "manifests" / "reports_manifest.csv"
REPORTS_DIR    = ROOT / "ammc_report_scraper" / "data" / "reports"


def ingest_scraped(force: bool = False) -> int:
    print("=" * 55)
    print("INGESTION DES RAPPORTS AMMC SCRAPES")
    print("=" * 55)

    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest introuvable : {MANIFEST_PATH}\n"
            "Lancez d'abord le scraper : cd ammc_report_scraper && python main.py"
        )
    if not REPORTS_DIR.is_dir():
        raise FileNotFoundError(f"Repertoire des rapports introuvable : {REPORTS_DIR}")

    from build_index import build_index

    added = build_index(force=force)

    print("\n" + "=" * 55)
    print(f"Ingestion terminée — {added} rapport(s) indexé(s).")
    print("=" * 55)
    return added


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingère les PDFs scrapés AMMC dans le pipeline RAG."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Réindexe tout (supprime l'ancien index)"
    )
    args = parser.parse_args()
    ingest_scraped(force=args.force)