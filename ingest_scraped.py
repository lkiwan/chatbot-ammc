"""
Bridge script: copies all downloaded PDFs from ammc_report_scraper into
data/pdfs/ with unique names  {company_normalized}_{year}.pdf,
saves data/scraper_meta.json, then builds (or updates) the ChromaDB index.

Usage:
    python ingest_scraped.py           # only new PDFs
    python ingest_scraped.py --force   # reindex everything from scratch
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "ammc_report_scraper" / "data" / "manifests" / "reports_manifest.csv"
PDFS_DIR      = ROOT / "data" / "pdfs"
META_PATH     = ROOT / "data" / "scraper_meta.json"


def _safe_stem(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_") or "unknown"


def load_manifest() -> pd.DataFrame:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest introuvable : {MANIFEST_PATH}\n"
            "Lancez d'abord le scraper : cd ammc_report_scraper && python main.py"
        )
    return pd.read_csv(MANIFEST_PATH, dtype=str, encoding="utf-8-sig")


def copy_pdfs(df: pd.DataFrame, force: bool) -> dict[str, dict]:
    """Copy each downloaded PDF to data/pdfs/{company}_{year}.pdf.
    Returns the metadata lookup dict (stem → metadata)."""
    PDFS_DIR.mkdir(parents=True, exist_ok=True)

    existing_meta: dict[str, dict] = {}
    if META_PATH.exists():
        existing_meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    done = df[df["download_status"].isin(["downloaded", "skipped"])].copy()
    copied = skipped = missing = 0

    for _, row in done.iterrows():
        local_path = Path(str(row.get("local_path", "")).strip())
        if not local_path.exists():
            missing += 1
            continue

        company_raw  = str(row.get("company_name", "")).strip()
        company_norm = _safe_stem(
            str(row.get("company_name_normalized", "")).strip() or company_raw
        )
        year = str(row.get("year", "")).strip()
        if not year or not company_norm:
            continue

        stem = f"{company_norm}_{year}"
        dest = PDFS_DIR / f"{stem}.pdf"

        if not dest.exists() or force:
            shutil.copy2(local_path, dest)
            copied += 1
        else:
            skipped += 1

        existing_meta[stem] = {
            "company":            company_raw,
            "company_normalized": company_norm,
            "year":               year,
            "sector":             str(row.get("sector", "")).strip(),
            "report_id":          str(row.get("report_id", "")).strip(),
            "source_url":         str(row.get("source_url", "")).strip(),
        }

    META_PATH.write_text(
        json.dumps(existing_meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print(f"  PDFs copiés    : {copied}")
    print(f"  Déjà présents  : {skipped}")
    print(f"  Fichiers manquants (encore en cours de scraping) : {missing}")
    print(f"  Total PDFs dans data/pdfs/ : {len(list(PDFS_DIR.glob('*.pdf')))}")
    print(f"  Métadonnées    : {META_PATH}")
    return existing_meta


def ingest_scraped(force: bool = False) -> int:
    print("=" * 55)
    print("INGESTION DES RAPPORTS AMMC SCRAPES")
    print("=" * 55)

    df = load_manifest()
    total_manifest = len(df)
    downloaded = len(df[df["download_status"].isin(["downloaded", "skipped"])])
    print(f"Manifest : {total_manifest} entrées, {downloaded} PDFs téléchargés\n")

    print("Phase 1 — Copie des PDFs vers data/pdfs/")
    copy_pdfs(df, force=force)

    print("\nPhase 2 — Extraction + indexation ChromaDB")
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
        help="Recopie et réindexe tout (supprime l'ancien index)"
    )
    args = parser.parse_args()
    ingest_scraped(force=args.force)
