FROM python:3.11-slim-bookworm

WORKDIR /app

ENV http_proxy=
ENV https_proxy=
ENV HTTP_PROXY=
ENV HTTPS_PROXY=

RUN apt-get update -o Acquire::Retries=3 && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    libmagic1 \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libreoffice \
    antiword \
    unrar-free \
    p7zip-full \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Копируем конфигурацию зависимостей из корня проекта
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

# Устанавливаем Playwright браузеры и их системные зависимости
RUN uv run playwright install --with-deps chromium

ENV PATH="/app/.venv/bin:$PATH"

COPY backend /app/backend

ENV OCR_LANGUAGES=none
ENV ENABLE_PDF_IMAGE_OCR=false

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
