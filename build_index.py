import csv
import json
from pathlib import Path

import chromadb

from config import (CHROMA_DIR, CHUNKS_DIR, GLOBAL_COLLECTION, PDFS_DIR,
                    RAW_DIR, REPORTS_JSON, SCRAPER_MANIFEST, SCRAPER_META_JSON,
                    SCRAPER_REPORTS_DIR)
from extract import extract, sanitize_stem


def load_scraper_meta() -> dict[str, dict]:
    if SCRAPER_META_JSON.exists():
        return json.loads(SCRAPER_META_JSON.read_text(encoding="utf-8"))
    return {}


def load_registry() -> list[dict]:
    if REPORTS_JSON.exists():
        return json.loads(REPORTS_JSON.read_text(encoding="utf-8"))
    return []


def save_registry(reg: list[dict]) -> None:
    REPORTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORTS_JSON.write_text(
        json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def save_scraper_meta(meta: dict[str, dict]) -> None:
    SCRAPER_META_JSON.parent.mkdir(parents=True, exist_ok=True)
    SCRAPER_META_JSON.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def find_pdfs() -> list[Path]:
    if not PDFS_DIR.is_dir():
        return []
    return sorted(PDFS_DIR.glob("*.pdf"))


def scraper_meta() -> dict[str, dict]:
    """Build stem -> metadata from the scraper manifest (one entry per report)."""
    if not SCRAPER_MANIFEST.exists():
        return {}
    meta: dict[str, dict] = {}
    with SCRAPER_MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            status = (row.get("download_status") or "").strip()
            if status not in ("downloaded", "skipped"):
                continue
            company_raw = (row.get("company_name") or "").strip()
            company_norm = sanitize_stem(
                (row.get("company_name_normalized") or "").strip() or company_raw
            )
            year = (row.get("year") or "").strip()
            if not company_norm or not year:
                continue
            stem = f"{company_norm}_{year}"
            meta[stem] = {
                "company": company_raw,
                "company_normalized": company_norm,
                "year": year,
                "sector": (row.get("sector") or "").strip(),
                "report_id": (row.get("report_id") or "").strip(),
                "source_url": (row.get("source_url") or "").strip(),
            }
    return meta


def iter_reports() -> list[dict]:
    """Yield report descriptors {pdf, stem, meta} from the scraper's nested
    reports dir on disk (works regardless of manifest freshness)."""
    meta_all = scraper_meta()
    reports: list[dict] = []
    if SCRAPER_REPORTS_DIR.is_dir():
        for pdf in sorted(SCRAPER_REPORTS_DIR.rglob("*.pdf")):
            rel = pdf.relative_to(SCRAPER_REPORTS_DIR)
            parts = rel.parts
            if len(parts) != 4:  # {sector}/{company}/{year}/annual_report.pdf
                continue
            sector, company_dir, year, _ = parts
            stem_base = sanitize_stem(company_dir)
            stem = f"{stem_base}_{year}"
            meta = meta_all.get(stem, {})
            if not meta:
                meta = {
                    "company": company_dir,
                    "company_normalized": stem_base,
                    "year": year,
                    "sector": sector,
                    "report_id": "",
                    "source_url": "",
                }
            reports.append(
                {"pdf": pdf, "stem": stem, "meta": meta, "relative": rel}
            )
    return reports


def ensure_chunks(pdf: Path, force: bool, stem: str | None = None) -> dict:
    stem = stem or sanitize_stem(pdf.name)
    chunks_path = CHUNKS_DIR / f"{stem}.json"
    csv_path = RAW_DIR / stem / f"{stem}.csv"
    if not force and chunks_path.exists() and csv_path.exists():
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        return {
            "stem": stem,
            "pdf": pdf.name,
            "pages": len(chunks) and max(c["page"] for c in chunks),
            "csv_rows": sum(1 for _ in csv_path.open(encoding="utf-8")) - 1,
            "chunks": len(chunks),
            "added": None,
        }
    return extract(pdf, stem=stem)


def build_index(force: bool = False) -> int:
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if force:
        try:
            client.delete_collection(GLOBAL_COLLECTION)
            print("Ancien index global supprime.")
        except Exception:
            pass
    collection = client.get_or_create_collection(GLOBAL_COLLECTION)

    save_scraper_meta(scraper_meta())

    reg = load_registry()
    known = {r["stem"] for r in reg}
    added = 0

    sources: list[tuple[str, Path, dict]] = []
    for r in iter_reports():
        sources.append((r["stem"], r["pdf"], r["meta"]))
    for pdf in find_pdfs():
        stem = sanitize_stem(pdf.name)
        if any(s == stem for s, _, _ in sources):
            continue
        sources.append((stem, pdf, scraper_meta().get(stem, {})))

    for stem, pdf, meta in sources:
        if stem in known and not force:
            continue
        info = ensure_chunks(pdf, force, stem=stem)
        chunks = json.loads((CHUNKS_DIR / f"{stem}.json").read_text(encoding="utf-8"))

        ids = [f"{stem}::{c['id']}" for c in chunks]
        docs = [c["text"] for c in chunks]
        metas = [
            {
                "report":             stem,
                "page":               c["page"],
                "source":             pdf.name,
                "company":            meta.get("company", stem),
                "company_normalized": meta.get("company_normalized", stem),
                "year":               meta.get("year", ""),
                "sector":             meta.get("sector", ""),
            }
            for c in chunks
        ]
        for i in range(0, len(ids), 64):
            collection.upsert(
                ids=ids[i : i + 64], documents=docs[i : i + 64], metadatas=metas[i : i + 64]
            )

        reg = [r for r in reg if r["stem"] != stem]
        reg.append({**info, "indexed": True})
        known.add(stem)
        added += 1
        print(f"Indexe : {stem} ({len(chunks)} chunks)")
        if added % 5 == 0:
            save_registry(reg)

    save_registry(reg)
    save_scraper_meta(scraper_meta())
    if added == 0:
        print(f"Rien a reindexer ({collection.count()} chunks au total).")
    else:
        print(f"Index global : {collection.count()} chunks -> {CHROMA_DIR}")
    return added


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    build_index(force=args.force)