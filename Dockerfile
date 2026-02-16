# Multi-stage Dockerfile for PromptQL MCP Server
# Optimized for production deployment with dashboard support

# Stage 1: Builder
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy setup.py and create minimal README if doesn't exist
COPY setup.py ./
RUN echo "# PromptQL MCP Server" > README.md

# Copy application code
COPY pgql ./pgql

# Install dependencies and build wheel (including dashboard extras)
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels ".[dashboard]"

# Stage 2: Runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl && \
    rm -rf /wheels

# Copy application code
COPY pgql ./pgql

# Create non-root user and data directory
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser

# Health check — verify HTTP server is actually responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8765/api/health || exit 1

# Expose dashboard port (if running in dashboard mode)
EXPOSE 8765

# Default command: start dashboard (override with "run" for MCP stdio mode)
ENTRYPOINT ["python", "-m", "pgql"]
CMD ["dashboard", "--host", "0.0.0.0", "--port", "8765"]
