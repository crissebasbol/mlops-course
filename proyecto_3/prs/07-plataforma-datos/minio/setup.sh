#!/bin/sh
# Crea buckets, políticas y usuarios de MinIO. Es idempotente: se ejecuta en cada sincronización.
set -eu

until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; do
  echo "Esperando a MinIO..."
  sleep 5
done

for bucket in mlflow landing datasets; do
  mc mb --ignore-existing "local/$bucket"
done

ensure_user() {
  user="$1" secret="$2" policy="$3"
  mc admin policy create local "$policy" "/policies/$policy.json"
  mc admin user add local "$user" "$secret"
  case "$(mc admin user info local "$user" --json)" in
    *"\"$policy\""*) echo "Política $policy ya asignada a $user" ;;
    *) mc admin policy attach local "$policy" --user "$user" ;;
  esac
}

ensure_user "$MLFLOW_ACCESS_KEY" "$MLFLOW_SECRET_KEY" mlflow-artifacts
ensure_user "$AIRFLOW_ACCESS_KEY" "$AIRFLOW_SECRET_KEY" airflow-data
ensure_user "$LOCUST_ACCESS_KEY" "$LOCUST_SECRET_KEY" locust-replay

mc ls local
mc admin user list local
