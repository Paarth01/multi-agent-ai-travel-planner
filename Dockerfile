FROM python:3.12-slim

WORKDIR /app

# Only install what the running app needs (skip pandas/fakeredis —
# those are dev-only, for scripts/ and tests/ respectively). Pinned
# directly rather than via `-c requirements.txt`, since pip's
# constraints-file mode rejects extras syntax like uvicorn[standard]
# ("Constraints cannot have extras") — a real bug I hit deploying this.
RUN pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.52.0" \
    pydantic==2.13.4 \
    pydantic-settings==2.14.2 \
    langgraph==1.2.10 \
    httpx==0.28.1 \
    redis==8.1.0

COPY schemas/ schemas/
COPY graph/ graph/
COPY api/ api/
COPY clients/ clients/
COPY cache/ cache/
COPY config.py .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
