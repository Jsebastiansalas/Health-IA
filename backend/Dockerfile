FROM python:3.12-slim

# Tesseract OCR con datos de español (OCR selectivo del Paso 5).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# El codificador cl100k_base de tiktoken se descarga en el build, no en tiempo de ejecución.
ENV TIKTOKEN_CACHE_DIR=/app/.tiktoken
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

RUN useradd --system --uid 1001 medtender \
    && mkdir -p /var/medtender-ephemeral \
    && chown -R medtender /app /var/medtender-ephemeral \
    && chmod 700 /var/medtender-ephemeral
USER medtender

EXPOSE 8000
# Imagen compartida por la API (por defecto) y el worker (command en docker-compose).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
