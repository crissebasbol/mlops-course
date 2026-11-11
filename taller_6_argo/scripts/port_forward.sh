#!/usr/bin/env bash
# Uso: ./taller_6_argo/scripts/port_forward.sh [start|stop|status]
# Publica la UI de Argo CD y la API del taller 6 en 10.43.97.106. Cada port-forward se relanza solo.
set -euo pipefail
cd "$(dirname "$0")/.."

CONTEXT=${CONTEXT:-kind-taller6}
LOGS=scripts/.port_forward
FORWARDS=(
  "8006 argocd svc/argocd-server 443"
  "8005 taller6 svc/taller6-housing 8000"
)

start() {
  mkdir -p "$LOGS"
  for F in "${FORWARDS[@]}"; do
    read -r LOCAL NS TARGET REMOTE <<< "$F"
    nohup bash -c "while true; do kubectl --context $CONTEXT -n $NS port-forward --address 0.0.0.0 $TARGET $LOCAL:$REMOTE; sleep 2; done" \
      > "$LOGS/$LOCAL.log" 2>&1 &
    echo $! > "$LOGS/$LOCAL.pid"
    echo "$LOCAL -> $NS/$TARGET:$REMOTE"
  done
}

stop() {
  for PID in "$LOGS"/*.pid; do
    [ -f "$PID" ] && kill "$(cat "$PID")" 2>/dev/null || true
    rm -f "$PID"
  done
  for F in "${FORWARDS[@]}"; do
    read -r LOCAL NS TARGET _ <<< "$F"
    pkill -f "kubectl --context $CONTEXT -n $NS port-forward --address 0.0.0.0 $TARGET" || true
  done
}

status() {
  for F in "${FORWARDS[@]}"; do
    read -r LOCAL NS TARGET _ <<< "$F"
    if curl -sk -o /dev/null --max-time 2 "https://127.0.0.1:$LOCAL" || curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$LOCAL/health"; then
      echo "OK    $LOCAL $NS/$TARGET"
    else
      echo "FALLA $LOCAL $NS/$TARGET"
    fi
  done
}

case "${1:-start}" in
  start) stop; start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Uso: $0 [start|stop|status]"; exit 1 ;;
esac
