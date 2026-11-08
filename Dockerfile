# Web-mode image for facility-log:
#
#   docker build -t ghcr.io/rlanak/facility-log:latest .
#
# Published automatically for each version tag by .github/workflows/docker-image.yml.

# --- 1. Build the Rust save reader (tools/save-parser) for Linux -------------
FROM rust:1-slim AS parser
WORKDIR /src
COPY tools/save-parser/Cargo.toml tools/save-parser/Cargo.lock ./
COPY tools/save-parser/src ./src
RUN cargo build --release

# --- 2. The app ----------------------------------------------------------------
FROM python:3.13-slim
# libglib2.0-0 / libgomp1: runtime libs for OpenCV / onnxruntime.
# apt-get upgrade: Debian security fixes newer than the base image (e.g. zlib).
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The app runs as this unprivileged user (uid/gid 1000), never as root —
# see docker-entrypoint.sh.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY data/foxhole ./data/foxhole
COPY run.py .
COPY --from=parser /src/target/release/foxhole-save-parser /usr/local/bin/foxhole-save-parser
ENV FOXHOLE_SAVE_PARSER=/usr/local/bin/foxhole-save-parser
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

# The user's data (SQLite + uploads) goes to a volume, not /app/data (that
# would hide the bundled catalog) — see docker-compose.yml.
ENV FACILITY_LOG_DATA_DIR=/data
# On a server the app refuses to start without the Discord login configured
# (app/main.py) — never open to the internet by a missing .env.
ENV FACILITY_LOG_REQUIRE_LOGIN=1
EXPOSE 8000
# --proxy-headers: behind Cloudflare Tunnel / a reverse proxy, so the app sees
# the real scheme and client (the session cookie is https-only when
# DISCORD_REDIRECT_URI is https).
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
