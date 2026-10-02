"""Central configuration, loaded from environment variables (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

CORPUS_DIR = (BACKEND_DIR / os.getenv("CORPUS_DIR", "../corpus")).resolve()
INDEX_DIR = (BACKEND_DIR / os.getenv("INDEX_DIR", "./data/index")).resolve()
AUDIT_LOG_PATH = (BACKEND_DIR / os.getenv("AUDIT_LOG_PATH", "./data/audit_log.jsonl")).resolve()
GRAPH_EDGES_PATH = (CORPUS_DIR / "graph_edges.json").resolve()
GRAPH_DIR = (BACKEND_DIR / os.getenv("GRAPH_DIR", "./data/graph")).resolve()
DENSE_DIR = (BACKEND_DIR / os.getenv("DENSE_DIR", "./data/dense")).resolve()
INGEST_DIR = (BACKEND_DIR / os.getenv("INGEST_DIR", "./data/ingest")).resolve()
VERIFY_REPORT_PATH = INGEST_DIR / "verify_report.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY", "").strip()
BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID", "").strip()
BHASHINI_PIPELINE_ID = os.getenv("BHASHINI_PIPELINE_ID", "").strip()

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

CONFIDENCE_HIGH_THRESHOLD = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.14"))
CONFIDENCE_MEDIUM_THRESHOLD = float(os.getenv("CONFIDENCE_MEDIUM_THRESHOLD", "0.085"))

DISCLAIMER = (
    "IP-SAKTI Sahayak provides general information to help you understand Indian and "
    "international IP / regulatory frameworks relevant to Ayurveda. It is NOT legal advice "
    "and does not create a lawyer-client or any professional relationship. Always verify "
    "against the cited primary source and consult a qualified IP attorney or registered "
    "patent/TM agent before making a filing, commercial or compliance decision."
)

TOP_K = int(os.getenv("TOP_K", "5"))
