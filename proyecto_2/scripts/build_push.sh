#!/usr/bin/env bash
# Uso: ./scripts/build_push.sh [version] [componente ...]
# Ejemplos:
#   ./scripts/build_push.sh                 # todas las imagenes con tag 1.0.0
#   ./scripts/build_push.sh 1.0.1 api       # solo la API con tag 1.0.1
# Requiere `docker login` con la cuenta de Docker Hub.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:-1.0.0}
shift || true
COMPONENTS=("$@")
[ ${#COMPONENTS[@]} -gt 0 ] || COMPONENTS=(airflow mlflow api streamlit locust)

REPO=${DOCKERHUB_USER:-crissebasbol}
PLATFORMS=${PLATFORMS:-linux/amd64}

for C in "${COMPONENTS[@]}"; do
  echo "== $REPO/proyecto2-$C:$VERSION ($PLATFORMS)"
  docker buildx build --platform "$PLATFORMS" \
    -t "$REPO/proyecto2-$C:$VERSION" \
    -t "$REPO/proyecto2-$C:latest" \
    --push "$C"
done
