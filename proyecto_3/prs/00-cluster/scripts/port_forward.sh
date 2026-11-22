#!/usr/bin/env bash
# Publica las UIs del clúster en los puertos 80xx de la VM de entrada (.106), los únicos abiertos
# hacia afuera. Cada port-forward se relanza solo si el pod se reinicia.
# Uso: ./scripts/port_forward.sh [start|stop|status]
set -euo pipefail
cd "$(dirname "$0")/.."

NS="${NAMESPACE:-housing-mlops}"
LOGS=scripts/.port_forward
FORWARDS=(
  "8002 $NS svc/airflow-api-server 8080"
  "8003 $NS svc/mlflow 5000"
  "8004 $NS svc/minio 9001"
  "8005 $NS svc/api 8000"
  "8006 argocd svc/argocd-server 443"
  "8007 $NS svc/streamlit 8501"
  "8008 $NS svc/grafana 3000"
  "8009 $NS svc/prometheus 9090"
  "8010 $NS svc/locust 8089"
  "8011 $NS svc/data-api 80"
)

start() {
  mkdir -p "$LOGS"
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  for forward in "${FORWARDS[@]}"; do
    read -r local_port namespace target remote_port <<< "$forward"
    nohup bash -c "while true; do kubectl -n $namespace port-forward --address 0.0.0.0 \
      $target $local_port:$remote_port; sleep 2; done" > "$LOGS/$local_port.log" 2>&1 &
    echo $! > "$LOGS/$local_port.pid"
    echo "http://$ip:$local_port -> $namespace/$target:$remote_port"
  done
}

stop() {
  for pid_file in "$LOGS"/*.pid; do
    [[ -f "$pid_file" ]] || continue
    kill "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file"
  done
  pkill -f "port-forward --address 0.0.0.0" || true
}

status() {
  for forward in "${FORWARDS[@]}"; do
    read -r local_port namespace target _ <<< "$forward"
    if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$local_port" \
      || curl -sk -o /dev/null --max-time 2 "https://127.0.0.1:$local_port"; then
      echo "OK    $local_port $namespace/$target"
    else
      echo "FALLA $local_port $namespace/$target"
    fi
  done
}

case "${1:-start}" in
  start) stop; start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Uso: $0 [start|stop|status]" >&2; exit 1 ;;
esac
