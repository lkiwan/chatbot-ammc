import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
PDFS_DIR = DATA_DIR / "pdfs"
RAW_DIR = DATA_DIR / "raw"
CHUNKS_DIR = DATA_DIR / "chunks"
REPORTS_JSON = DATA_DIR / "reports.json"

CHROMA_DIR = ROOT / ".chroma"
GLOBAL_COLLECTION = "rapports"

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50

LLM_API_KEY = os.environ.get("GROQ_API_KEY", "")
LLM_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

TOP_K = 10
HISTORY_LIMIT = 8