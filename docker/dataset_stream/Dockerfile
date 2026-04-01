FROM python:3.12-slim

WORKDIR /app

COPY dataset_stream/requirements.txt ./dataset_stream/
COPY database-service/requirements.txt ./database-service/
RUN pip install --no-cache-dir \
    -r dataset_stream/requirements.txt \
    -r database-service/requirements.txt

# common + database-service (services, models, repositories for route expansion)
COPY common ./common
COPY database-service ./database-service
COPY dataset_stream ./dataset_stream
COPY dataset_stream/.env ./.env

ENV PYTHONPATH=/app/database-service:/app

EXPOSE 8010

CMD ["uvicorn", "dataset_stream.main:app", "--host", "0.0.0.0", "--port", "8010"]
