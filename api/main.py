import csv
import json
import secrets
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # api/ dir for local modules

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analytics import append_event, get_summary

from build_index import (build_index, find_pdfs, iter_reports, load_registry,
                         load_scraper_meta)
from chat import answer, answer_stream_tokens, invalidate, load_store
from config import (API_TOKEN, CHUNKS_DIR, CORS_ORIGINS, LLM_MODEL, PDFS_DIR,
                    RATE_LIMIT_PER_MIN, RAW_DIR, WATCH_ENABLED)
from extract import sanitize_stem

# Optional PostgreSQL-backed retrieval (graceful degradation if DB not running)
try:
    from db.session import check_connection
    from retrieval.hybrid_retriever import HybridRetriever
    from retrieval.sql_retriever import SQLRetriever
    _DB_AVAILABLE = check_connection()
except Exception:
    _DB_AVAILABLE = False

_hybrid: Optional["HybridRetriever"] = None
_sql: Optional["SQLRetriever"] = None

def _get_hybrid() -> "HybridRetriever":
    global _hybrid
    if _hybrid is None:
        from retrieval.hybrid_retriever import HybridRetriever
        _hybrid = HybridRetriever()
    return _hybrid

def _get_sql() -> "SQLRetriever":
    global _sql
    if _sql is None:
        from retrieval.sql_retriever import SQLRetriever
        _sql = SQLRetriever()
    return _sql

WATCH_INTERVAL = 4
_INGEST_LOCK = threading.Lock()
_FAILED: dict[str, float] = {}


@asynccontextmanager
async def _lifespan(app):
    if WATCH_ENABLED:
        threading.Thread(target=_watch_directory, daemon=True).start()
    yield


app = FastAPI(
    title="Module d'analyse des publications financieres AMMC",
    version="1.0.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CHAT_PATHS = {"/api/chat", "/api/chat/stream"}
_PDF_PATH = "/api/pdf"
_RATE_HITS: dict[str, deque[float]] = {}
_RATE_LOCK = threading.Lock()


@app.middleware("http")
async def _api_guard(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path.startswith("/api"):
        if API_TOKEN:
            provided = request.headers.get("x-api-token", "")
            auth = request.headers.get("authorization", "")
            if auth[:7].lower() == "bearer ":
                provided = auth[7:].strip()
            if not provided and request.method == "GET" and request.url.path.rstrip("/") == _PDF_PATH:
                provided = request.query_params.get("token", "")
            if not secrets.compare_digest(provided, API_TOKEN):
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        if request.url.path.rstrip("/") in _CHAT_PATHS:
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            with _RATE_LOCK:
                hits = _RATE_HITS.setdefault(ip, deque())
                while hits and now - hits[0] > 60:
                    hits.popleft()
                if len(hits) >= RATE_LIMIT_PER_MIN:
                    return JSONResponse(
                        {"detail": "trop de requetes, reessayez dans un instant"},
                        status_code=429,
                    )
                hits.append(now)
    return await call_next(request)

DIST = ROOT / "frontend" / "dist"


def _pending_pdfs(stems: set[str]) -> list[Path]:
    pending = []
    for r in iter_reports():
        stem = r["stem"]
        if stem in stems:
            continue
        p = r["pdf"]
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
            pending_map = {
                r["stem"]: r["pdf"] for r in iter_reports() if r["pdf"] in pending
            }
            if not pending_map:
                pending_map = {sanitize_stem(p.name): p for p in pending}
            for stem, p in pending_map.items():
                try:
                    _FAILED[stem] = p.stat().st_mtime
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


class TrackRequest(BaseModel):
    type: str  # "visit" | "demo_login" | "demo_message"


@app.post("/api/track")
async def track(req: TrackRequest, request: Request):
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    append_event(req.type, ua=ua, ip=ip)
    return {"ok": True}


@app.get("/api/analytics")
def analytics():
    return get_summary()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    rapport: str | None = None
    company: str | None = None
    year: str | None = None
    sector: str | None = None


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


@app.get("/api/pdfs")
def pdfs():
    meta = load_scraper_meta()
    indexed = {r["stem"] for r in load_registry()}
    out = []
    for stem, m in meta.items():
        if stem not in indexed:
            continue
        if not m.get("document_url"):
            continue
        out.append({
            "stem": stem,
            "company": m.get("company", stem),
            "company_normalized": m.get("company_normalized", stem),
            "year": m.get("year", ""),
            "sector": m.get("sector", ""),
            "url": m["document_url"],
        })
    out.sort(key=lambda r: (r["company"], int(r["year"] or 0), r["stem"]))
    return out


@app.get("/api/pdf")
async def pdf_proxy(request: Request):
    """Proxy un PDF AMMC pour l'afficher dans la visionneuse integree.

    Le serveur source envoie `X-Frame-Options: SAMEORIGIN`, donc on ne peut pas
    l'encadrer directement depuis le navigateur : on transit par notre backend
    (meme origine) en retirant l'entete bloquant et en relayant le Range.
    """
    url = request.query_params.get("url", "")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL PDF invalide.")
    try:
        host = (url.split("/")[2] or "").split(":")[0].lower()
    except Exception:
        host = ""
    if not host.endswith("ammc.ma"):
        raise HTTPException(status_code=400, detail="Domaine PDF non autorise.")

    headers = {}
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(300.0, connect=20.0),
        headers={"User-Agent": "Mozilla/5.0 (compatible; AMMC-Chatbot/1.0)"},
    )
    try:
        resp = await client.send(client.build_request("GET", url, headers=headers), stream=True)
    except Exception as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"PDF injoignable : {type(exc).__name__}")

    if resp.status_code >= 400:
        await client.aclose()
        raise HTTPException(status_code=502, detail="PDF indisponible.")

    out_headers = {
        "Content-Type": "application/pdf",
        "Content-Disposition": "inline",
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
    }
    if resp.status_code == 206 and resp.headers.get("content-range"):
        out_headers["Content-Range"] = resp.headers["content-range"]

    async def stream():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(stream(), status_code=resp.status_code, headers=out_headers)


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


@app.get("/api/companies")
def companies():
    meta = load_scraper_meta()
    indexed = {r["stem"] for r in load_registry()}
    seen: dict[str, dict] = {}
    for stem, m in meta.items():
        if stem not in indexed:
            continue
        key = m.get("company_normalized", stem)
        if key not in seen:
            seen[key] = {
                "company": m.get("company", key),
                "company_normalized": key,
                "sector": m.get("sector", ""),
                "years": [],
            }
        year = m.get("year", "")
        if year and year not in seen[key]["years"]:
            seen[key]["years"].append(year)
    result = sorted(seen.values(), key=lambda x: x["company"])
    for r in result:
        r["years"] = sorted(r["years"], reverse=True)
    return result


@app.post("/api/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message vide.")
    reply, sources = answer(
        request.message,
        request.history,
        rapport=request.rapport,
        company=request.company,
        year=request.year,
        sector=request.sector,
    )
    return {"role": "assistant", "content": reply, "sources": sources}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message vide.")

    def generate():
        for token, sources in answer_stream_tokens(
            request.message,
            request.history,
            rapport=request.rapport,
            company=request.company,
            year=request.year,
            sector=request.sector,
        ):
            if sources is not None:
                yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"
            else:
                yield f"data: {json.dumps({'token': token})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/db/status")
def db_status():
    """Check PostgreSQL availability."""
    try:
        from db.session import check_connection
        ok = check_connection()
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    return {"available": ok}


@app.get("/api/companies/db")
def companies_db(sector: Optional[str] = Query(None)):
    """List companies from PostgreSQL (requires DB)."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="PostgreSQL not available")
    result = _get_sql().list_companies(sector=sector)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)
    return result.rows


@app.get("/api/companies/{company_slug}/metrics")
def company_metrics(
    company_slug: str,
    year: Optional[int] = Query(None),
    metric: Optional[str] = Query(None),
):
    """Get financial metrics for a company from PostgreSQL."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="PostgreSQL not available")
    sql = _get_sql()
    if metric:
        result = sql.get_metric(company_slug, metric, year)
    else:
        result = sql.compare_metric_across_years(company_slug, metric or "net_income")
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)
    return {"company": company_slug, "rows": result.rows, "count": result.row_count}


@app.get("/api/companies/{company_slug}/financials")
def company_financials(company_slug: str, year: int = Query(...)):
    """Get all financial statements for a company/year from PostgreSQL."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="PostgreSQL not available")
    sql = _get_sql()
    income  = sql.get_income_statement(company_slug, year)
    balance = sql.get_balance_sheet(company_slug, year)
    cashflow = sql.get_cash_flow(company_slug, year)
    ratios  = sql.get_financial_ratios(company_slug, year)
    return {
        "company": company_slug,
        "year":    year,
        "income_statement": income.rows[0] if income.rows else None,
        "balance_sheet":    balance.rows[0] if balance.rows else None,
        "cash_flow":        cashflow.rows[0] if cashflow.rows else None,
        "ratios":           ratios.rows,
    }


@app.get("/api/companies/{company_slug}/shareholders")
def company_shareholders(
    company_slug: str,
    year: Optional[int] = Query(None),
):
    """Get shareholder structure for a company."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="PostgreSQL not available")
    result = _get_sql().get_shareholders(company_slug, year=year)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)
    return result.rows


@app.post("/api/search")
def hybrid_search(request: "ChatRequest"):
    """
    Hybrid search: route to SQL and/or vector based on question type.
    Returns raw retrieval results (not LLM-generated).
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message vide.")

    year_int = None
    try:
        year_int = int(request.year) if request.year else None
    except ValueError:
        pass

    if _DB_AVAILABLE:
        result = _get_hybrid().retrieve(
            request.message,
            company=request.company,
            year=year_int,
            sector=request.sector,
        )
        return {
            "query_type": result.query_type,
            "confidence": result.router_result.confidence,
            "reasoning":  result.router_result.reasoning,
            "sql_rows":   result.sql_result.rows if result.sql_result else [],
            "chunks":     result.vector_result.chunks[:5] if result.vector_result else [],
        }
    else:
        # Fallback: vector only
        from chat import retrieve as _retrieve
        chunks = _retrieve(
            request.message,
            company=request.company,
            year=request.year,
            sector=request.sector,
        )
        return {
            "query_type": "vector",
            "confidence": 0.5,
            "reasoning":  "PostgreSQL not available — vector only",
            "sql_rows":   [],
            "chunks":     chunks[:5] if chunks else [],
        }


if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="frontend")