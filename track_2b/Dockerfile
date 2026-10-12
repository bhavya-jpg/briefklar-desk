# --- frontend build ---
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ .
RUN npm run build

# --- app ---
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 fontconfig \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY src/ src/
COPY bench/ bench/
COPY tests/ tests/
COPY --from=web /web/build /app/static
# kept next to the build so the token-contrast and font-licence tests run inside the image
COPY frontend/src/lib/design/tokens.css frontend/src/lib/design/tokens.css
COPY frontend/static/fonts/ /usr/share/fonts/briefklar/
RUN fc-cache -f
ENV PYTHONPATH=/app/src:/app PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 XDG_CACHE_HOME=/tmp/cache \
    BRIEFKLAR_STATIC_DIR=/app/static
EXPOSE 8080
CMD ["uvicorn", "briefklar.main:app", "--host", "0.0.0.0", "--port", "8080"]
