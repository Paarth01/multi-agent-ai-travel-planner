FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic -c requirements.txt

COPY data_service/ data_service/

EXPOSE 8100

CMD ["uvicorn", "data_service.app:app", "--host", "0.0.0.0", "--port", "8100"]
