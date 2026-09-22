import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

from config import CHUNKS_DIR, CHUNK_OVERLAP, CHUNK_SIZE, RAW_DIR

MAX_COLS = 12


def sanitize_stem(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "rapport"


def sanitize(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value


def is_real_table(rows: list[list]) -> bool:
    real = [r for r in rows if any(sanitize(c) for c in r)]
    if len(real) < 3:
        return False
    widths = {sum(1 for c in r if sanitize(c)) for r in real[:6]}
    return len(widths) > 0


def extract_tables(page, page_idx: int) -> list[list[list]]:
    tables = []
    for table in page.extract_tables():
        rows = [[sanitize(c) for c in row] for row in table]
        if is_real_table(rows):
            tables.append(rows)
    return tables


def markdown_table(rows: list[list], page_idx: int, table_idx: int) -> str:
    collapsed = []
    for row in rows:
        cells = [c for c in row if c]
        collapsed.append(" | ".join(cells))
    return f"Tableau p.{page_idx} n°{table_idx} :\n" + "\n".join(collapsed)


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        if end < len(words):
            near = max(start, end - 100)
            cut = -1
            for i in range(near, end - 1, -1):
                if words[i].endswith((".", "!", "?", ":")):
                    cut = i + 1
                    break
            if cut > start:
                end = cut
        chunk = " ".join(words[start:end])
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


def extract(pdf: Path) -> dict:
    if not pdf.exists():
        raise FileNotFoundError(f"PDF introuvable : {pdf}")

    stem = sanitize_stem(pdf.name)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = RAW_DIR / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{stem}.csv"
    chunks_path = CHUNKS_DIR / f"{stem}.json"

    print(f"Extraction de : {pdf.name} (rapport « {stem} »)")

    csv_rows = []
    chunks: list[dict] = []
    chunk_id = 0

    with pdfplumber.open(pdf) as p:
        for page_idx, page in enumerate(p.pages, start=1):
            text = page.extract_text() or ""
            tables = extract_tables(page, page_idx)

            for t_idx, rows in enumerate(tables, start=1):
                for row_idx, row in enumerate(rows):
                    cells = [c for c in row if c][:MAX_COLS]
                    cells += [""] * (MAX_COLS - len(cells))
                    csv_rows.append([page_idx, t_idx, row_idx] + cells)

            body = text
            for t_idx, rows in enumerate(tables, start=1):
                body += "\n\n" + markdown_table(rows, page_idx, t_idx)

            for piece in chunk_text(body, CHUNK_SIZE, CHUNK_OVERLAP):
                chunks.append(
                    {
                        "id": chunk_id,
                        "page": page_idx,
                        "report": stem,
                        "text": piece,
                        "source": pdf.name,
                    }
                )
                chunk_id += 1

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        header = ["page", "tableau", "ligne"] + [f"col{i}" for i in range(1, MAX_COLS + 1)]
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(csv_rows)

    with chunks_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)

    print(f"  CSV    -> {csv_path} ({len(csv_rows)} lignes)")
    print(f"  Chunks -> {chunks_path} ({len(chunks)} morceaux)")

    return {
        "stem": stem,
        "pdf": pdf.name,
        "pages": len(pdfplumber.open(pdf).pages),
        "csv_rows": len(csv_rows),
        "chunks": len(chunks),
        "added": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    from config import PDFS_DIR

    pdfs = sorted((PDFS_DIR or Path("data/pdfs")).glob("*.pdf"))
    if not pdfs:
        raise SystemExit("Aucun PDF dans data/pdfs/. De posez-y un rapport puis relancez.")
    for pdf in pdfs:
        extract(pdf)