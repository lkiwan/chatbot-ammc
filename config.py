import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

# ── Paths ───────────────────────────────────────────────────────────────────
DATA_DIR = ROOT / "data"
PDFS_DIR = DATA_DIR / "pdfs"
RAW_DIR = DATA_DIR / "raw"
CHUNKS_DIR = DATA_DIR / "chunks"
REPORTS_JSON = DATA_DIR / "reports.json"
SCRAPER_META_JSON = DATA_DIR / "scraper_meta.json"
SCRAPER_MANIFEST = ROOT / "ammc_report_scraper" / "data" / "manifests" / "reports_manifest.csv"
SCRAPER_COMPANIES = ROOT / "ammc_report_scraper" / "data" / "companies" / "companies.csv"
SCRAPER_REPORTS_DIR = ROOT / "ammc_report_scraper" / "data" / "reports"

# ── ChromaDB ────────────────────────────────────────────────────────────────
CHROMA_DIR = ROOT / ".chroma"
GLOBAL_COLLECTION = "rapports"

# ── Extraction ──────────────────────────────────────────────────────────────
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
EXTRACTION_CONFIDENCE_THRESHOLD = float(os.environ.get("EXTRACTION_CONFIDENCE_THRESHOLD", "0.4"))
EXTRACTION_DEBUG = os.environ.get("EXTRACTION_DEBUG", "false").lower() == "true"

# ── LLM ─────────────────────────────────────────────────────────────────────
LLM_API_KEY = os.environ.get("GROQ_API_KEY", "")
LLM_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── RAG ─────────────────────────────────────────────────────────────────────
TOP_K = int(os.environ.get("TOP_K", "10"))
HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT", "8"))

# ── PostgreSQL ──────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://ammc:ammc_secret@localhost:5432/ammc_finance",
)