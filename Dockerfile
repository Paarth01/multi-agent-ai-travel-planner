FROM python:3.12-slim

WORKDIR /app

# Only install what the running app needs (skip pandas/fakeredis —
# those are dev-only, for scripts/ and tests/ respectively).
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] pydantic pydantic-settings langgraph httpx redis \
    -c requirements.txt

COPY schemas/ schemas/
COPY graph/ graph/
COPY api/ api/
COPY clients/ clients/
COPY cache/ cache/
COPY config.py .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
