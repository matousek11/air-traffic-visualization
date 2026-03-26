FROM python:3.12-slim

WORKDIR /app

COPY dataset_stream/requirements.txt ./dataset_stream/
RUN pip install --no-cache-dir -r dataset_stream/requirements.txt

# Copy shared package and dataset_stream service.
COPY common ./common
COPY dataset_stream ./dataset_stream
COPY dataset_stream/.env ./.env

ENV PYTHONPATH=/app

EXPOSE 8010

CMD ["uvicorn", "dataset_stream.main:app", "--host", "0.0.0.0", "--port", "8010"]
