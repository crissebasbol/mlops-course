#!/usr/bin/env bash
# Uso: ./scripts/deploy.sh
# Despliega todo en el namespace proyecto2: primero los manifiestos (kustomize) y luego
# Airflow con Helm. Se corre desde la VM que tiene kubectl + helm (10.43.97.106).
set -euo pipefail
cd "$(dirname "$0")/.."

NS=proyecto2

kubectl apply -k .

for STS in postgres-data postgres-mlflow postgres-airflow minio; do
  kubectl -n "$NS" rollout status "statefulset/$STS" --timeout=10m
done
kubectl -n "$NS" wait --for=condition=complete job/minio-init --timeout=5m || true
for DEPLOY in mlflow api streamlit locust prometheus grafana; do
  kubectl -n "$NS" rollout status "deployment/$DEPLOY" --timeout=10m
done

helm repo add apache-airflow https://airflow.apache.org >/dev/null 2>&1 || true
helm repo update apache-airflow
helm upgrade --install airflow apache-airflow/airflow \
  --version 1.22.0 \
  --namespace "$NS" \
  -f airflow/values.yaml \
  --wait --timeout 20m

kubectl -n "$NS" get pods -o wide
