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

COPY backend/certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend

ENV OCR_LANGUAGES=none
ENV ENABLE_PDF_IMAGE_OCR=false

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
