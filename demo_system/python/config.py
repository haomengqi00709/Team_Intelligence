import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR        = Path(__file__).parent.parent.parent   # /Team intelligence/
DEMO_DIR        = Path(__file__).parent                  # /demo_system/python/

# DATA_DIR points to the persistent volume on Railway (or local dirs in dev)
_DATA_DIR       = Path(os.getenv("DATA_DIR", str(DEMO_DIR)))
CACHE_DIR       = _DATA_DIR / "cache"
UPLOADS_DIR     = _DATA_DIR / "uploads"
CHROMA_DIR      = _DATA_DIR / "chroma_db"
LOGS_DIR        = _DATA_DIR / "logs"
GRAPH_PATH      = CACHE_DIR / "knowledge_graph.json"

# Ensure all data directories exist
for _d in [CACHE_DIR, UPLOADS_DIR, CHROMA_DIR, LOGS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Data source folders → (path, source_label)
DATA_SOURCES = {
    "email":    ROOT_DIR / "Email" / "eml",
    "meetings": ROOT_DIR / "meetings",
    "work":     ROOT_DIR / "Work",
    "guide":    ROOT_DIR / "guide",
}

# Folders to skip when walking
EXCLUDE_DIRS = {"archive", "__pycache__", ".git"}

# File extensions to skip
EXCLUDE_EXTENSIONS = {".py", ".json", ".md"}

# Specific filenames to skip
EXCLUDE_FILES = {"convert_work_files.py", "json_to_eml.py"}

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL         = "models/gemini-embedding-001"
GENERATION_MODEL_FLASH  = "gemini-2.0-flash"
GENERATION_MODEL_PRO    = "gemini-2.5-pro"

# ── ChromaDB ─────────────────────────────────────────────────────────────────
CHROMA_COLLECTION = "team_intelligence"

# ── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZES = {
    "email":          300,
    "meeting_minutes": 400,
    "word_doc":       512,
    "sas_script":     None,   # split by PROC/DATA block
    "excel_sheet":    200,
    "csv":            200,
    "policy_doc":     600,
    "log_file":       400,
    "powerpoint":     400,
}
CHUNK_OVERLAP = 128

# ── Demo ─────────────────────────────────────────────────────────────────────
DEMO_MODE = False   # set True to serve cached responses only
TOP_K     = 10      # default retrieval count
