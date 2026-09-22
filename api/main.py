import csv
import json
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from build_index import build_index, find_pdfs, load_registry
from chat import answer, invalidate, load_store
from config import CHUNKS_DIR, LLM_MODEL, PDFS_DIR, RAW_DIR
from extract import sanitize_stem

WATCH_INTERVAL = 4
_INGEST_LOCK = threading.Lock()
_FAILED: dict[str, float] = {}


@asynccontextmanager
async def _lifespan(app):
    threading.Thread(target=_watch_directory, daemon=True).start()
    yield


app = FastAPI(
    title="Module d'analyse des publications financieres AMMC",
    version="1.0.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST = ROOT / "frontend" / "dist"


def _pending_pdfs(stems: set[str]) -> list[Path]:
    pending = []
    for p in find_pdfs():
        stem = sanitize_stem(p.name)
        if stem in stems:
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if _FAILED.get(stem) == mtime:
            continue
        pending.append(p)
    return pending


def _ingest_new() -> int:
    with _INGEST_LOCK:
        stems = {r["stem"] for r in load_registry()}
        pending = _pending_pdfs(stems)
        if not pending:
            return 0
        try:
            n = build_index(force=False)
            if n:
                invalidate()
                _FAILED.clear()
            return n
        except Exception as exc:
            for p in pending:
                try:
                    _FAILED[sanitize_stem(p.name)] = p.stat().st_mtime
                except OSError:
                    pass
            print(f"[ingest] {type(exc).__name__}: {exc}")
            return 0


def _watch_directory() -> None:
    while True:
        time.sleep(WATCH_INTERVAL)
        try:
            n = _ingest_new()
            if n:
                print(f"[watch] {n} nouveau(x) rapport(s) indexe(s)")
        except Exception as exc:
            print(f"[watch] {type(exc).__name__}: {exc}")


def _total_counts():
    reg = {}
    try:
        reg = {r["stem"]: r for r in load_registry()}
    except Exception:
        reg = {}
    store = load_store()
    chunks = 0
    try:
        chunks = store.count() if store else 0
    except Exception:
        chunks = 0
    return reg, store, chunks


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    rapport: str | None = None


def _read_csv(name: str) -> list[dict]:
    path = RAW_DIR / name / f"{name}.csv"
    if not path.exists():
        return []
    tables: dict[tuple[int, int], list[list[str]]] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (int(row["page"]), int(row["tableau"]))
            cols = [
                row[f"col{i}"].strip()
                for i in range(1, 13)
                if row.get(f"col{i}", "").strip()
            ]
            if any(cols):
                tables.setdefault(key, []).append(cols)
    return [
        {"rapport": name, "page": p, "table": t, "rows": rows[:60]}
        for (p, t), rows in sorted(tables.items())
    ]


@app.get("/api/health")
def health():
    _, store, chunks = _total_counts()
    return {
        "ok": True,
        "model": LLM_MODEL,
        "rapports": len(load_registry()),
        "index": chunks > 0,
        "chunks": chunks,
    }


@app.get("/api/reports")
def reports():
    reg, store, chunks = _total_counts()
    items = list(reg.values())
    total_pages = sum(r.get("pages") or 0 for r in items)
    total_rows = sum(r.get("csv_rows") or 0 for r in items)
    return {
        "rapports": items,
        "total": {
            "rapports": len(items),
            "pages": total_pages,
            "chunks": chunks,
            "csv_rows": total_rows,
            "index": chunks > 0,
        },
    }


@app.post("/api/ingest")
def ingest():
    try:
        n = _ingest_new()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")
    reg, _, chunks = _total_counts()
    return {"added": n, "total_chunks": chunks, "rapports": len(reg)}


@app.get("/api/metrics")
def metrics():
    path = ROOT / "data" / "metrics.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/tables")
def tables(rapport: str | None = None):
    if rapport:
        names = [rapport]
    else:
        pdfs = sorted(p.stem for p in PDFS_DIR.glob("*.pdf")) if PDFS_DIR.is_dir() else []
        names = [r["stem"] for r in load_registry()] or pdfs
    out: list[dict] = []
    for name in names:
        out.extend(_read_csv(name))
    return out


@app.get("/api/chunks")
def chunks(rapport: str | None = None):
    out: list[dict] = []
    for f in sorted(CHUNKS_DIR.glob("*.json")):
        if rapport and f.stem != rapport:
            continue
        for c in json.loads(f.read_text(encoding="utf-8")):
            out.append({"rapport": c.get("report", f.stem), "page": c["page"], "text": c["text"]})
    return out[:500]


@app.post("/api/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message vide.")
    reply, sources = answer(request.message, request.history, rapport=request.rapport)
    return {"role": "assistant", "content": reply, "sources": sources}


if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="frontend")