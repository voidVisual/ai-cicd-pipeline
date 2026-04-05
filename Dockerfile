FROM python:3.11-slim AS base

# Create a non-root user — security best practice
# Running as root inside a container is a HIGH severity finding
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# Set working directory
WORKDIR /app

# ── Stage 2: install dependencies ──────────────────────
# Copy ONLY requirements first — Docker layer cache trick
# If requirements.txt hasn't changed, this layer is cached
# and re-builds are much faster
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 3: copy application code ─────────────────────
# Copy app code AFTER deps — keeps code changes from
# busting the expensive pip install layer
COPY app/ ./app/

# ── Stage 4: security hardening ────────────────────────
# Drop to non-root user before running anything
USER appuser

# Expose the app port (documentation only — doesn't open firewall)
EXPOSE 8000

# Health check — ECS uses this to know if container is alive
# Checks every 30s, fails after 3 misses → container is replaced
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
