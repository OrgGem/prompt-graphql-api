FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY setup.py README.md ./
COPY promptql_mcp_server ./promptql_mcp_server

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python", "-m", "promptql_mcp_server", "run"]
