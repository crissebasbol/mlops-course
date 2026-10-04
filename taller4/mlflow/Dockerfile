FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV MLFLOW_S3_ENDPOINT_URL=http://minio:9000 \
    AWS_ACCESS_KEY_ID=admin \
    AWS_SECRET_ACCESS_KEY=admin123 \
    BACKEND_STORE_URI=postgresql://mlflow:mlflow123@postgres-mlflow:5432/mlflow \
    ARTIFACT_ROOT=s3://mlflows3/artifacts

RUN uv pip install --system --no-cache mlflow==3.16.1 boto3 "psycopg[binary]"

WORKDIR /app

EXPOSE 5000

CMD mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri "$BACKEND_STORE_URI" \
    --default-artifact-root "$ARTIFACT_ROOT" \
    --serve-artifacts
