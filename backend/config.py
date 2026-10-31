import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
INBOX_DIR = DATA_DIR / "inbox"
PAGE_CACHE_DIR = DATA_DIR / "page_cache"
BRIEFS_DIR = DATA_DIR / "briefs"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "benchsplit.db")))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT_DIR / DATABASE_PATH

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "15"))
PROMPT_VERSION = "v1.0"

STATUTE_NAMES = {
    "NI_ACT_S138": "Section 138, Negotiable Instruments Act, 1881",
    "ARB_ACT_S11": "Section 11(6), Arbitration & Conciliation Act, 1996",
    "CRPC_S482": "Section 482, Code of Criminal Procedure, 1973",
    "REAL_CORPUS": "Real judgment corpus · imported source records",
}

REAL_DATA_DIR = ROOT_DIR / "database_real_github" / "data"
MOCK_DATA_MODE = os.getenv("MOCK_DATA_MODE", "").strip().lower() in {"1", "true", "yes"}

for directory in (DATA_DIR, RAW_PDFS_DIR, INBOX_DIR, PAGE_CACHE_DIR, BRIEFS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
