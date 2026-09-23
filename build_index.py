import json
from pathlib import Path

import chromadb

from config import (CHROMA_DIR, CHUNKS_DIR, GLOBAL_COLLECTION, PDFS_DIR,
                    RAW_DIR, REPORTS_JSON, SCRAPER_META_JSON)
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


def find_pdfs() -> list[Path]:
    if not PDFS_DIR.is_dir():
        return []
    return sorted(PDFS_DIR.glob("*.pdf"))


def ensure_chunks(pdf: Path, force: bool) -> dict:
    stem = sanitize_stem(pdf.name)
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
    return extract(pdf)


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

    reg = load_registry()
    known = {r["stem"] for r in reg}
    added = 0
    scraper_meta = load_scraper_meta()

    for pdf in find_pdfs():
        stem = sanitize_stem(pdf.name)
        if stem in known and not force:
            continue
        info = ensure_chunks(pdf, force)
        chunks = json.loads((CHUNKS_DIR / f"{stem}.json").read_text(encoding="utf-8"))

        ids = [f"{stem}::{c['id']}" for c in chunks]
        docs = [c["text"] for c in chunks]
        meta = scraper_meta.get(stem, {})
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

    save_registry(reg)
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