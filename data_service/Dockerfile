FROM python:3.12-slim

WORKDIR /app

# Pinned directly rather than via `-c requirements.txt` — pip's
# constraints-file mode rejects extras syntax like uvicorn[standard]
# ("Constraints cannot have extras").
RUN pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.52.0" \
    pydantic==2.13.4

COPY data_service/ data_service/

EXPOSE 8100

CMD ["uvicorn", "data_service.app:app", "--host", "0.0.0.0", "--port", "8100"]
