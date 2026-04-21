FROM node:22-slim AS builder

WORKDIR /build

COPY web-server/package.json web-server/yarn.lock ./
RUN yarn install --frozen-lockfile

COPY web-server/ ./
RUN yarn build

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=builder /build/static ./web-server/static
COPY web-server/views ./web-server/views
COPY web-server/main.py ./web-server/main.py

EXPOSE 8000

WORKDIR /app/web-server

CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]
