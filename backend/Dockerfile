# syntax=docker/dockerfile:1.7

FROM python:3.11-slim-bookworm AS base

WORKDIR /app

ENV http_proxy=
ENV https_proxy=
ENV HTTP_PROXY=
ENV HTTPS_PROXY=
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"

ARG INSTALL_OCR=false
ARG INSTALL_PLAYWRIGHT=false
ARG INSTALL_STT=true

RUN set -eux; \
    apt-get update -o Acquire::Retries=3; \
    apt-get install -y --no-install-recommends ca-certificates libgomp1 libmagic1; \
    if [ "$INSTALL_STT" = "true" ]; then \
        apt-get install -y --no-install-recommends ffmpeg; \
    fi; \
    if [ "$INSTALL_OCR" = "true" ]; then \
        apt-get install -y --no-install-recommends \
            tesseract-ocr \
            tesseract-ocr-rus \
            tesseract-ocr-eng \
            libreoffice \
            antiword \
            unrar-free \
            p7zip-full; \
    fi; \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS builder

ARG UV_EXTRAS="stt"

COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    extras_args=""; \
    for extra in $UV_EXTRAS; do \
        extras_args="$extras_args --extra $extra"; \
    done; \
    uv sync --frozen --no-dev $extras_args

FROM base AS runtime

ARG INSTALL_PLAYWRIGHT=false
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY --from=builder /app/.venv /app/.venv
COPY backend /app/backend

RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
        uv run playwright install chromium; \
    fi

ENV OCR_LANGUAGES=none
ENV ENABLE_PDF_IMAGE_OCR=false

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
