#!/bin/sh
# Arma la URI de Postgres desde variables de entorno para que la contraseña no aparezca en el manifiesto.
set -eu

exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --workers "${MLFLOW_WORKERS:-2}" \
  --backend-store-uri "postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT:-5432}/${POSTGRES_DB}" \
  --artifacts-destination "${ARTIFACTS_DESTINATION}" \
  --serve-artifacts
