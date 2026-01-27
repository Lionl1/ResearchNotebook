# HyperbookLM (Python)

Local research assistant built on FastAPI with vLLM for LLM calls, embeddings-based
search, and local STT for audio transcription. Includes a lightweight browser UI served by the
backend for quick testing.

## Features

- URL scraping and PDF/TXT uploads
- Extended file parsing via `extract-text` (DOCX/PPTX/XLSX/RTF/etc.)
- Embeddings indexing + search over all sources
- Summary, mindmap, slides generation
- Streaming chat
- Audio transcription (STT)

## Quick Start (Local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.local.example .env.local
uvicorn backend.app.main:app --reload --port 8080
```

Open: `http://localhost:8080`

More details: `backend/README.md`

## Quick Start (Docker)

```bash
docker build -t hyperbooklm-backend -f backend/Dockerfile .
docker run --env-file .env.local -p 8080:8000 hyperbooklm-backend
```

Container-only run (no local venv):

```bash
docker run --env-file .env.local -p 8080:8000 hyperbooklm-backend
```

If vLLM runs on the host, set:

```bash
VLLM_API_BASE=http://host.docker.internal:8080/v1
```

## Environment

Required:
- `VLLM_API_BASE` (default: `http://localhost:8000/v1`)
- `VLLM_API_KEY` (default: `sk`)
- `VLLM_MODEL` (default: `Qwen/Qwen2.5-7B-Instruct`)
Embeddings (local):
- `EMBEDDINGS_MODEL` (default: `intfloat/multilingual-e5-base`)
- `EMBEDDINGS_DEVICE` (default: `cpu`)

Local STT:
- `STT_PROVIDER=faster-whisper`
- `STT_MODEL=small` (or local model path)
- `STT_DEVICE=cpu`
- `STT_COMPUTE_TYPE=int8`
- `STT_BEAM_SIZE=5`

Optional:
- `CORS_ORIGINS`
- `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_SOURCE_CHARS`, `SEARCH_TOP_K`
- `CHROMA_DIR` (default: `.chroma`, ChromaDB storage)
- `MAX_IMPORT_SIZE_MB`, `MAX_IMPORT_UNPACK_MB`, `MAX_IMPORT_FILES` (import limits)
- `GEMINI_API_KEY`, `VEO_MODEL` for `/api/veo/*`

## Project Structure

```
hyperbooklm/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── static/
│   │   │   ├── index.html
│   │   │   ├── styles.css
│   │   │   └── app.js
│   └── requirements.txt
├── .env.local.example
└── README.md
```

## Export / Import

- Export a project as a zip (includes `projects.json` and optional `vectors.json`).
- Import a zip to restore projects and embeddings.

UI: use **Export Project** / **Import Project** in the Sources panel.

## Open Source Projects Used

- FastAPI: https://fastapi.tiangolo.com
- Uvicorn: https://www.uvicorn.org
- httpx: https://www.python-httpx.org
- Pydantic: https://docs.pydantic.dev
- ChromaDB: https://www.trychroma.com
- sentence-transformers: https://www.sbert.net
- LangChain Text Splitters: https://python.langchain.com
- PyMuPDF: https://pymupdf.readthedocs.io
- BeautifulSoup4: https://www.crummy.com/software/BeautifulSoup
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- extract-text: https://github.com/Diversus23/extract-text
- HyperbookLLM: https://github.com/hyperbrowserai/hyperbooklm
- pdfplumber: https://github.com/jsvine/pdfplumber
- python-docx: https://python-docx.readthedocs.io
- python-pptx: https://python-pptx.readthedocs.io
- Pillow: https://python-pillow.org
- pytesseract: https://github.com/madmaze/pytesseract

## License

MIT
