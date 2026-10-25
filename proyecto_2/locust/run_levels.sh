#!/usr/bin/env bash
# Uso: ./run_levels.sh <usuarios> [usuarios ...]
# Ejemplo: ./run_levels.sh 10 30 60 100 150 200 300
# Corre Locust en modo headless dentro del pod de Locust (en el nodo data, lejos de la API),
# un nivel por cada cantidad de usuarios, y agrega una fila por nivel a resultados/resumen.csv.
# En paralelo guarda `kubectl top` de los pods de la API en resultados/top_<nivel>.csv.
set -euo pipefail
cd "$(dirname "$0")"

[ $# -gt 0 ] || { echo "Indique al menos un nivel de usuarios"; exit 1; }

NS=${NAMESPACE:-proyecto2}
API_HOST=${API_HOST:-http://api:8000}
SPAWN_RATE=${SPAWN_RATE:-20}
STABLE_SECONDS=${STABLE_SECONDS:-120}
COOLDOWN=${COOLDOWN:-30}
MAX_FAIL_PCT=${MAX_FAIL_PCT:-1}
MAX_P95_MS=${MAX_P95_MS:-500}

REPLICAS=$(kubectl -n "$NS" get deploy api -o jsonpath='{.spec.replicas}')
POD=$(kubectl -n "$NS" get pod -l app=locust -o jsonpath='{.items[0].metadata.name}')

mkdir -p resultados
RESUMEN=resultados/resumen.csv
ENCABEZADO="replicas,usuarios,spawn_rate,rps,peticiones,exitosas,fallos,fallos_pct,promedio_ms,p50_ms,p95_ms,p99_ms,cumple,inicio_epoch,fin_epoch"
[ -f "$RESUMEN" ] || echo "$ENCABEZADO" > "$RESUMEN"

for USERS in "$@"; do
  RAMP=$(( (USERS + SPAWN_RATE - 1) / SPAWN_RATE ))
  RUN_TIME=$(( RAMP + STABLE_SECONDS ))
  NAME="rep${REPLICAS}_u${USERS}"
  echo "== $NAME: $USERS usuarios, spawn-rate $SPAWN_RATE, ${RAMP}s de rampa + ${STABLE_SECONDS}s estables"

  ( end=$(( $(date +%s) + RUN_TIME )); echo "epoch,pod,cpu,memoria" > "resultados/top_${NAME}.csv"
    while [ "$(date +%s)" -lt "$end" ]; do
      kubectl -n "$NS" top pod -l app=api --no-headers 2>/dev/null \
        | awk -v t="$(date +%s)" '{print t","$1","$2","$3}' >> "resultados/top_${NAME}.csv"
      sleep 5
    done ) &
  TOP_PID=$!

  kubectl -n "$NS" exec "$POD" -- locust -f /locust/locustfile.py \
    --headless \
    --host "$API_HOST" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "${RUN_TIME}s" \
    --reset-stats \
    --csv "/tmp/$NAME" \
    --only-summary || true
  FIN=$(date +%s)
  INICIO=$(( FIN - STABLE_SECONDS ))
  wait "$TOP_PID" || true

  for SUFFIX in stats failures exceptions; do
    kubectl -n "$NS" cp "$POD:/tmp/${NAME}_${SUFFIX}.csv" "resultados/${NAME}_${SUFFIX}.csv" >/dev/null 2>&1 || true
  done

  awk -F, -v rep="$REPLICAS" -v users="$USERS" -v sr="$SPAWN_RATE" -v maxf="$MAX_FAIL_PCT" -v maxp="$MAX_P95_MS" \
    -v ini="$INICIO" -v fin="$FIN" '
    NR == 1 { for (i = 1; i <= NF; i++) { gsub(/"/, "", $i); col[$i] = i }; next }
    { gsub(/"/, "") }
    $col["Name"] == "Aggregated" {
      n = $col["Request Count"]; f = $col["Failure Count"]
      pct = (n > 0) ? 100 * f / n : 100
      p95 = $col["95%"]
      ok = (pct < maxf && p95 < maxp) ? "si" : "no"
      printf "%s,%s,%s,%.1f,%d,%d,%d,%.2f,%.1f,%s,%s,%s,%s,%s,%s\n", rep, users, sr, $col["Requests/s"], n, n - f, f, pct, $col["Average Response Time"], $col["50%"], p95, $col["99%"], ok, ini, fin
    }' "resultados/${NAME}_stats.csv" | tee -a "$RESUMEN"

  sleep "$COOLDOWN"
done

echo
column -s, -t < "$RESUMEN"
