#!/usr/bin/env bash
# Uso: ./scripts/port_forward.sh [start|stop|status]
# Publica las UIs del clúster en los puertos 80xx de esta VM (10.43.97.106), que son los
# unicos abiertos hacia afuera. Cada port-forward se relanza solo si el pod se reinicia.
set -euo pipefail
cd "$(dirname "$0")/.."

NS=${NAMESPACE:-proyecto2}
LOGS=scripts/.port_forward
FORWARDS=(
  "8002 svc/airflow-api-server 8080"
  "8003 svc/mlflow 5000"
  "8004 svc/minio 9001"
  "8005 svc/api 8000"
  "8007 svc/streamlit 8501"
  "8008 svc/grafana 3000"
  "8009 svc/prometheus 9090"
  "8010 svc/locust 8089"
)

start() {
  mkdir -p "$LOGS"
  for F in "${FORWARDS[@]}"; do
    read -r LOCAL TARGET REMOTE <<< "$F"
    nohup bash -c "while true; do kubectl -n $NS port-forward --address 0.0.0.0 $TARGET $LOCAL:$REMOTE; sleep 2; done" \
      > "$LOGS/$LOCAL.log" 2>&1 &
    echo $! > "$LOGS/$LOCAL.pid"
    echo "http://$(hostname -I 2>/dev/null | awk '{print $1}'):$LOCAL -> $TARGET:$REMOTE"
  done
}

stop() {
  for PID in "$LOGS"/*.pid; do
    [ -f "$PID" ] && kill "$(cat "$PID")" 2>/dev/null || true
    rm -f "$PID"
  done
  pkill -f "kubectl -n $NS port-forward --address 0.0.0.0" || true
}

status() {
  for F in "${FORWARDS[@]}"; do
    read -r LOCAL TARGET _ <<< "$F"
    if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$LOCAL"; then echo "OK    $LOCAL $TARGET"; else echo "FALLA $LOCAL $TARGET"; fi
  done
}

case "${1:-start}" in
  start) stop; start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Uso: $0 [start|stop|status]"; exit 1 ;;
esac
