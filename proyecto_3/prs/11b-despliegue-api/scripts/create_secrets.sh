#!/usr/bin/env bash
# Crea o actualiza los Secrets del namespace a partir de un .env local (nunca versionado).
# Uso: cp .env.example .env && editar valores && ./scripts/create_secrets.sh [.env]
set -euo pipefail

ENV_FILE="${1:-.env}"
[[ -f "$ENV_FILE" ]] || { echo "No existe $ENV_FILE: copiar .env.example y completar los valores" >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

NAMESPACE="${NAMESPACE:-housing-mlops}"

require() {
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || { echo "Falta $name en $ENV_FILE" >&2; exit 1; }
  done
}

apply_secret() {
  local name="$1"
  shift
  kubectl -n "$NAMESPACE" create secret generic "$name" "$@" --dry-run=client -o yaml \
    | kubectl apply -f - >/dev/null
  echo "Secret $name aplicado en $NAMESPACE"
}

require KUBE_CONTEXT
current_context="$(kubectl config current-context)"
if [[ "$current_context" != "$KUBE_CONTEXT" ]]; then
  echo "El contexto actual es '$current_context' y se esperaba '$KUBE_CONTEXT'. No se aplica nada." >&2
  exit 1
fi

kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

require POSTGRES_DATA_PASSWORD AIRFLOW_ETL_PASSWORD API_WRITER_PASSWORD APP_READER_PASSWORD
apply_secret postgres-data \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_DATA_PASSWORD" \
  --from-literal=AIRFLOW_ETL_PASSWORD="$AIRFLOW_ETL_PASSWORD" \
  --from-literal=API_WRITER_PASSWORD="$API_WRITER_PASSWORD" \
  --from-literal=APP_READER_PASSWORD="$APP_READER_PASSWORD"

require POSTGRES_MLFLOW_PASSWORD
apply_secret postgres-mlflow --from-literal=POSTGRES_PASSWORD="$POSTGRES_MLFLOW_PASSWORD"

require MINIO_ROOT_USER MINIO_ROOT_PASSWORD MINIO_MLFLOW_SECRET_KEY MINIO_AIRFLOW_SECRET_KEY \
  MINIO_LOCUST_SECRET_KEY
apply_secret minio-root \
  --from-literal=MINIO_ROOT_USER="$MINIO_ROOT_USER" \
  --from-literal=MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD"
apply_secret minio-mlflow \
  --from-literal=AWS_ACCESS_KEY_ID=mlflow \
  --from-literal=AWS_SECRET_ACCESS_KEY="$MINIO_MLFLOW_SECRET_KEY"
apply_secret minio-airflow \
  --from-literal=AWS_ACCESS_KEY_ID=airflow \
  --from-literal=AWS_SECRET_ACCESS_KEY="$MINIO_AIRFLOW_SECRET_KEY"
apply_secret minio-locust \
  --from-literal=AWS_ACCESS_KEY_ID=locust \
  --from-literal=AWS_SECRET_ACCESS_KEY="$MINIO_LOCUST_SECRET_KEY"

require POSTGRES_AIRFLOW_PASSWORD AIRFLOW_ADMIN_PASSWORD AIRFLOW_API_SECRET_KEY AIRFLOW_JWT_SECRET \
  AIRFLOW_FERNET_KEY
apply_secret postgres-airflow --from-literal=POSTGRES_PASSWORD="$POSTGRES_AIRFLOW_PASSWORD"
apply_secret airflow-metadata \
  --from-literal=connection="postgresql://airflow:${POSTGRES_AIRFLOW_PASSWORD}@postgres-airflow:5432/airflow"
apply_secret airflow-fernet-key --from-literal=fernet-key="$AIRFLOW_FERNET_KEY"
apply_secret airflow-api-secret-key --from-literal=api-secret-key="$AIRFLOW_API_SECRET_KEY"
apply_secret airflow-jwt-secret --from-literal=jwt-secret="$AIRFLOW_JWT_SECRET"
apply_secret airflow-admin --from-literal=password="$AIRFLOW_ADMIN_PASSWORD"

require API_ADMIN_TOKEN
apply_secret api-admin --from-literal=token="$API_ADMIN_TOKEN"
