# Web-mode image for facility-log. Build context is the PARENT folder, because
# the game-save reader lives in the sibling repo ../foxhole-msupps-parser:
#
#   docker compose up -d --build        (from this folder; see docker-compose.yml)
#
# or by hand, from E:\projetos\foxhole:
#   docker build -f facility-log/Dockerfile -t facility-log .

# --- 1. Build the Rust save reader for Linux ---------------------------------
FROM rust:1-slim AS parser
WORKDIR /src
COPY foxhole-msupps-parser/Cargo.toml foxhole-msupps-parser/Cargo.lock ./
COPY foxhole-msupps-parser/src ./src
RUN cargo build --release

# --- 2. The app ----------------------------------------------------------------
FROM python:3.13-slim
# tesseract-ocr: the legacy OCR engine (RapidOCR is the default and needs
# nothing extra). libglib2.0-0 / libgomp1: runtime libs for OpenCV / onnxruntime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY facility-log/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY facility-log/app ./app
COPY facility-log/web ./web
COPY facility-log/data/foxhole ./data/foxhole
COPY facility-log/run.py .
COPY --from=parser /src/target/release/foxhole-msupps-parser /usr/local/bin/foxhole-msupps-parser
ENV FOXHOLE_SAVE_PARSER=/usr/local/bin/foxhole-msupps-parser

# The user's data (SQLite + uploads) goes to a volume, not /app/data (that
# would hide the bundled catalog) — see docker-compose.yml.
ENV FACILITY_LOG_DATA_DIR=/data
EXPOSE 8000
# --proxy-headers: behind Cloudflare Tunnel / a reverse proxy, so the app sees
# the real scheme and client (the session cookie is https-only when
# DISCORD_REDIRECT_URI is https).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
