FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN uv pip install --system --no-cache mlflow==3.16.1 boto3 "psycopg[binary]"

WORKDIR /app

EXPOSE 5000

CMD mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --workers "${MLFLOW_WORKERS:-2}" \
    --backend-store-uri "$BACKEND_STORE_URI" \
    --artifacts-destination "$ARTIFACTS_DESTINATION" \
    --serve-artifacts
