# Python Backend (FastAPI)

Single-service backend that serves a lightweight UI, handles ingestion, indexing,
search, and LLM calls via a local vLLM server. Chunking uses LangChain utilities
and vectors are stored in ChromaDB. File parsing is расширен через интеграцию
с `extract-text` (see `backend/third_party/extract-text`).

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8080
```

Open: `http://localhost:8080`

## Environment

Required for LLM:
- `VLLM_API_BASE` (default: `http://localhost:8000/v1`)
- `VLLM_API_KEY` (default: `sk`)
- `VLLM_MODEL` (default: `Qwen/Qwen2.5-7B-Instruct`)
Embeddings (local, CPU by default):
- `EMBEDDINGS_MODEL` (default: `intfloat/multilingual-e5-base`)
- `EMBEDDINGS_DEVICE` (default: `cpu`)

Local STT:
- `STT_PROVIDER=faster-whisper`
- `STT_MODEL=small` (or local model path)
- `STT_DEVICE=cpu`
- `STT_COMPUTE_TYPE=int8`
- `STT_BEAM_SIZE=5`

Optional:
- `CORS_ORIGINS` (comma-separated list, e.g. `http://localhost:3000`)
- `GEMINI_API_KEY` and `VEO_MODEL` for `/api/veo/*`
- `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_SOURCE_CHARS`, `SEARCH_TOP_K` for embeddings search
- `CHROMA_DIR` for Chroma persistence (default: `.chroma`)
- `DEFAULT_NOTEBOOK_ID` (default: `nb-1`)
- `OCR_LANGUAGES` for extract-text OCR (set to `none` to disable OCR)
- `ENABLE_PDF_IMAGE_OCR` to skip OCR for images embedded in PDFs

## UI Workflow

1) Add sources (URL or file) in the UI.
2) Click **Index Sources** (builds embeddings and stores them in ChromaDB).
3) Use **Embeddings Search** or Chat/Summary/Mindmap/Slides.

## Embeddings Search

Embeddings are computed locally via `sentence-transformers`. If the model name contains
`e5`, the backend automatically prefixes inputs with `query:` and `passage:`.

If you add sources via `/api/upload` or `/api/scrape`, the server caches them per
`notebookId`. Then you can index without sending the full source list.

1) Index sources (server-stored):
```bash
curl -X POST http://localhost:8080/api/index \
  -H "Content-Type: application/json" \
  -d '{"notebookId":"nb-1"}'
```

2) Query:
```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{"notebookId":"nb-1","query":"ваш вопрос","topK":5 }'
```

To reset the index, delete the `CHROMA_DIR` directory.

## API Reference (JSON)

- `POST /api/scrape`
  - Body: `{ "url": "https://...", "notebookId": "nb-1" }`
  - Stores the source server-side and returns `{ id, title, text, content, url }`.

- `POST /api/upload` (multipart/form-data)
  - Fields: `file` (PDF/TXT), optional `notebookId`
  - Stores the source server-side and returns `{ id, title, text, content, filename, pages }`.

- `POST /api/stt` (multipart/form-data)
  - Fields: `file` (audio), optional `notebookId`
  - Transcribes audio, stores as a source, and returns `{ text, segments, source }`.

- `POST /api/index`
  - Body: `{ "notebookId": "nb-1", "sources": [...] }` (sources optional)
  - If `sources` omitted, uses server-stored sources for the notebook.

- `POST /api/search`
  - Body: `{ "notebookId": "nb-1", "query": "text", "topK": 5 }`
  - Returns ranked chunks with scores and source metadata.

- `POST /api/sources`
  - Body: `{ "notebookId": "nb-1" }`
  - Returns cached sources for the notebook.

- `POST /api/sources/remove`
  - Body: `{ "notebookId": "nb-1", "sourceId": "source-..." }`
  - Removes a single source from the cache (reindex afterwards).

- `POST /api/sources/clear`
  - Body: `{ "notebookId": "nb-1" }`
  - Clears cached sources and deletes the Chroma index.

- `POST /api/summary`
  - Body: `{ "context": "..." }`

- `POST /api/chat`
  - Body: `{ "messages": [{ "role": "user", "content": "..." }], "context": "..." }`
  - Streams text tokens.

- `POST /api/gpt/mindmap`
  - Body: `{ "notebookId": "nb-1", "sources": [...] }`

- `POST /api/gemini/slides`
  - Body: `{ "notebookId": "nb-1", "sources": [...] }`

- `POST /api/veo/start` and `POST /api/veo/poll`
  - Require `GEMINI_API_KEY`.

- `POST /api/projects/export`
  - Body: `{ "projectId": "proj-..." }` (optional)
  - Returns a zip with `projects.json` and optional `vectors.json` (embeddings dump).

- `POST /api/projects/import`
  - Body: multipart form with `file` (zip), optional `mode` (`merge` or `replace`)
  - Restores `projects.json` and optional `vectors.json`.


## Notes

- Scraping uses `httpx` + `BeautifulSoup` (static HTML only, no JS execution).
- `/api/index` replaces the whole index for the notebook.
- Source cache is in memory; Chroma stores only embeddings + metadata.
- The embeddings model downloads on first use (Hugging Face cache inside the container).
- `extract-text` используется для расширенного парсинга файлов. Некоторые функции (OCR,
  архивы, Office) зависят от установленных библиотек и системных утилит.
  Для полного списка форматов в контейнере нужны `tesseract-ocr` (ru/en),
  `libreoffice`, `antiword`, `unrar-free`, `p7zip-full`, а также Python-пакет `werkzeug`.

## Tests

```bash
pip install -r backend/requirements.txt -r backend/requirements-test.txt
pytest backend/tests
```
