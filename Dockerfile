# ============================================================================
#  AKAZA X PROXY — Dockerfile
#  Multi-stage build on python:3.12-slim
# ============================================================================
FROM python:3.12-slim AS base

# --- System dependencies ---
# unrar      -> required by Python `rarfile` module
# p7zip-full -> fallback 7z extraction (py7zr is pure-Python but unrar-free
#               is also handy for edge cases)
# ca-certificates -> TLS verification for proxy testing
# curl        -> healthcheck inside the container
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        unrar \
        p7zip-full \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# --- Working directory ---
WORKDIR /app

# --- Install Python dependencies first (better Docker layer caching) ---
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.1.2 \
    && pip install --no-cache-dir -r requirements.txt

# --- Copy bot source ---
COPY AKAZA_X_PROXY_Bot.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# --- Persistent volume for users.json / working_proxies.json / logs ---
VOLUME ["/app/data"]

# --- Environment variables (override at runtime) ---
ENV API_ID=611335 \
    API_HASH=d524b414d21f4d37f08684c1df41ac9c \
    BOT_TOKEN= \
    ADMIN_ID= \
    WORK_DIR=/app/data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# --- Healthcheck (bot process alive?) ---
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD pgrep -f "AKAZA_X_PROXY_Bot.py" > /dev/null || exit 1

# --- Run as non-root user for security ---
RUN useradd -m -u 1000 akaza \
    && chown -R akaza:akaza /app
USER akaza

ENTRYPOINT ["./entrypoint.sh"]
