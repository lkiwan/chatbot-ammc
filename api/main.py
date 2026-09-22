import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat import answer, load_store
from config import (CHROMA_DIR, CSV_PATH, LLM_MODEL, PDF_PATH, PDF_STEM)

app = FastAPI(title="Module d'analyse des publications financieres AMMC", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST = ROOT / "frontend" / "dist"


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


def _load_csv_tables():
    if not CSV_PATH.exists():
        return []
    import csv

    tables: dict[tuple[int, int], list[list[str]]] = {}
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["page"]), int(row["tableau"]))
            cols = [
                row[f"col{i}"].strip()
                for i in range(1, 13)
                if row.get(f"col{i}", "").strip()
            ]
            if any(cols):
                tables.setdefault(key, []).append(cols)
    return [
        {"page": p, "table": t, "rows": rows[:60]}
        for (p, t), rows in sorted(tables.items())
    ]


@app.get("/api/health")
def health():
    collection = load_store()
    chunks = 0
    try:
        chunks = collection.count() if collection else 0
    except Exception:
        chunks = 0
    return {
        "ok": True,
        "model": LLM_MODEL,
        "report": PDF_PATH.name if PDF_PATH else None,
        "index": chunks > 0,
        "chunks": chunks,
    }


@app.get("/api/report")
def report():
    collection = load_store()
    chunks = 0
    try:
        chunks = collection.count() if collection else 0
    except Exception:
        chunks = 0
    pages = 0
    if PDF_PATH:
        try:
            from pypdf import PdfReader

            pages = len(PdfReader(str(PDF_PATH)).pages)
        except Exception:
            pages = 0
    return {
        "titre": "Attijariwafa bank — Resultats au 30 juin 2026",
        "emetteur": "Attijariwafa bank SA — Casablanca",
        "pdf": PDF_PATH.name if PDF_PATH else None,
        "pages": pages,
        "chunks": chunks,
        "csv_rows": _csv_row_count(),
        "index": chunks > 0,
    }


def _csv_row_count():
    if not CSV_PATH.exists():
        return 0
    return sum(1 for _ in CSV_PATH.open(encoding="utf-8")) - 1


@app.get("/api/metrics")
def metrics():
    path = ROOT / "data" / "metrics.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/tables")
def tables():
    return _load_csv_tables()


@app.get("/api/chunks")
def chunks(page: int | None = None):
    path = ROOT / "data" / "chunks.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if page:
        data = [c for c in data if c["page"] == page]
    return [{"page": c["page"], "text": c["text"]} for c in data]


@app.post("/api/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message vide.")
    reply, sources = answer(request.message, request.history)
    return {"role": "assistant", "content": reply, "sources": sources}


if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="frontend")