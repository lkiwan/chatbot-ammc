import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

PDF_PATH = next(ROOT.glob("*.pdf"), None)
PDF_STEM = (
    re.sub(r"[^a-z0-9]+", "_", PDF_PATH.stem.lower()).strip("_") if PDF_PATH else "rapport"
)

DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / f"{PDF_STEM}.csv"
CHUNKS_PATH = DATA_DIR / "chunks.json"

CHROMA_DIR = ROOT / ".chroma"
COLLECTION = PDF_STEM

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50

LLM_API_KEY = os.environ.get("GROQ_API_KEY", "")
LLM_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

TOP_K = 10
HISTORY_LIMIT = 8