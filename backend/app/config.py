import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env.local", override=False)


def env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    return value if value is not None else default


def env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


HF_TOKEN = env("HF_TOKEN", "") or ""
if HF_TOKEN and not os.getenv("HUGGING_FACE_HUB_TOKEN"):
    os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

VLLM_API_BASE = (env("VLLM_API_BASE", "http://localhost:8000/v1") or "").rstrip("/")
VLLM_API_KEY = env("VLLM_API_KEY", "sk")
VLLM_MODEL = env("VLLM_MODEL", "") 
EMBEDDINGS_MODEL = (
    env("EMBEDDINGS_MODEL")
    or env("VLLM_EMBEDDINGS_MODEL")
    or "intfloat/multilingual-e5-base"
)
EMBEDDINGS_DEVICE = env("EMBEDDINGS_DEVICE", "cpu") or "cpu"

LLM_TIMEOUT_SECONDS = env_float("LLM_TIMEOUT_SECONDS", 120.0)
LLM_MAX_TOKENS = env_int("LLM_MAX_TOKENS", 8192)
EMBEDDINGS_TIMEOUT_SECONDS = env_float("EMBEDDINGS_TIMEOUT_SECONDS", 60.0)

SCRAPE_USER_AGENT = env(
    "SCRAPE_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
)
SCRAPE_CA_CERT_PATH = env("SCRAPE_CA_CERT_PATH", "") or ""
REQUESTS_CA_BUNDLE = env("REQUESTS_CA_BUNDLE", "") or ""
if SCRAPE_CA_CERT_PATH and not os.getenv("REQUESTS_CA_BUNDLE") and not os.getenv("SSL_CERT_FILE"):
    os.environ["REQUESTS_CA_BUNDLE"] = SCRAPE_CA_CERT_PATH
SCRAPE_TIMEOUT_SECONDS = env_float("SCRAPE_TIMEOUT_SECONDS", 30.0)
MAX_SCRAPE_CHARS = env_int("MAX_SCRAPE_CHARS", 200000)
MAX_SOURCE_CHARS = env_int("MAX_SOURCE_CHARS", 200000)

CHUNK_SIZE = env_int("CHUNK_SIZE", 1500)
CHUNK_OVERLAP = env_int("CHUNK_OVERLAP", 200)
SEARCH_TOP_K = env_int("SEARCH_TOP_K", 5)

CHROMA_DIR = env("CHROMA_DIR", ".chroma") or ".chroma"

MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 100)
MAX_IMPORT_SIZE_MB = env_int("MAX_IMPORT_SIZE_MB", 200)
MAX_IMPORT_UNPACK_MB = env_int("MAX_IMPORT_UNPACK_MB", 600)
MAX_IMPORT_FILES = env_int("MAX_IMPORT_FILES", 4000)

STT_PROVIDER = env("STT_PROVIDER", "faster-whisper") or "faster-whisper"
STT_MODEL = env("STT_MODEL", "") or ""
STT_DEVICE = env("STT_DEVICE", "cpu") or "cpu"
STT_COMPUTE_TYPE = env("STT_COMPUTE_TYPE", "int8") or "int8"
STT_BEAM_SIZE = env_int("STT_BEAM_SIZE", 5)

GEMINI_API_KEY = env("GEMINI_API_KEY", "")
VEO_MODEL = env("VEO_MODEL", "")

CORS_ORIGINS = [
    origin.strip()
    for origin in (env("CORS_ORIGINS", "") or "").split(",")
    if origin.strip()
]

DEFAULT_NOTEBOOK_ID = env("DEFAULT_NOTEBOOK_ID", "nb-1") or "nb-1"
