FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
COPY database-service/requirements.txt ./database-service/requirements.txt
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r database-service/requirements.txt

COPY common ./common
COPY database-service ./database-service
COPY flight-simulation-server ./flight-simulation-server

ENV PYTHONPATH=/app:/app/database-service

WORKDIR /app/flight-simulation-server

EXPOSE 8001

CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8001"]
