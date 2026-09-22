import json
import re
from pathlib import Path

import pdfplumber

from config import CHUNKS_PATH, CHUNK_OVERLAP, CHUNK_SIZE, CSV_PATH, DATA_DIR, PDF_PATH

MAX_COLS = 12


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


def extract() -> None:
    if PDF_PATH is None:
        raise FileNotFoundError("Aucun PDF trouve dans le dossier projet.")
    print(f"Extraction de : {PDF_PATH.name}")

    DATA_DIR.mkdir(exist_ok=True)
    csv_rows = []
    chunks: list[dict] = []
    chunk_id = 0

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
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
                    {"id": chunk_id, "page": page_idx, "text": piece, "source": PDF_PATH.name}
                )
                chunk_id += 1

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        header = ["page", "tableau", "ligne"] + [f"col{i}" for i in range(1, MAX_COLS + 1)]
        writer = __import__("csv").writer(f)
        writer.writerow(header)
        writer.writerows(csv_rows)

    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)

    print(f"CSV      -> {CSV_PATH} ({len(csv_rows)} lignes)")
    print(f"Chunks   -> {CHUNKS_PATH} ({len(chunks)} morceaux)")


if __name__ == "__main__":
    extract()