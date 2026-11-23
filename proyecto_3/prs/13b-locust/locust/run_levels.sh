#!/usr/bin/env bash
# Prueba de carga por escalones con Locust headless dentro del pod de Locust.
# Uso: ./locust/run_levels.sh [usuarios ...]   (por defecto 10 50 100 200 300)
# Por cada escalón guarda las estadísticas de Locust, `kubectl top` de los pods de la API
# y una fila en locust/resultados/resumen.csv con los segundos de inicio y fin para Grafana.
set -euo pipefail
cd "$(dirname "$0")"

LEVELS=("$@")
[[ ${#LEVELS[@]} -gt 0 ]] || LEVELS=(10 50 100 200 300)

NS=${NAMESPACE:-housing-mlops}
API_HOST=${API_HOST:-http://api:8000}
SPAWN_RATE=${SPAWN_RATE:-20}
STABLE_SECONDS=${STABLE_SECONDS:-180}
COOLDOWN=${COOLDOWN:-30}
MAX_FAIL_PCT=${MAX_FAIL_PCT:-1}
MAX_P95_MS=${MAX_P95_MS:-500}

REPLICAS=$(kubectl -n "$NS" get deploy api -o jsonpath='{.spec.replicas}')
POD=$(kubectl -n "$NS" get pod -l app=locust -o jsonpath='{.items[0].metadata.name}')
CHAMPION=$(kubectl -n "$NS" exec "$POD" -c locust -- python -c \
  "import json, urllib.request; print(json.load(urllib.request.urlopen('$API_HOST/health'))['champion_version'])")
[[ "$CHAMPION" != "None" ]] || { echo "La API no tiene champion: /predict respondería 503" >&2; exit 1; }

mkdir -p resultados
SUMMARY=resultados/resumen.csv
HEADER="replicas,usuarios,spawn_rate,rps,peticiones,fallos,fallos_pct,promedio_ms,p50_ms,p95_ms,p99_ms,cumple,champion,inicio_epoch,fin_epoch"
[[ -f "$SUMMARY" ]] || echo "$HEADER" > "$SUMMARY"

for USERS in "${LEVELS[@]}"; do
  RAMP=$(( (USERS + SPAWN_RATE - 1) / SPAWN_RATE ))
  RUN_TIME=$(( RAMP + STABLE_SECONDS ))
  NAME="rep${REPLICAS}_u${USERS}"
  echo "== $NAME: $USERS usuarios, ${RAMP} s de rampa y ${STABLE_SECONDS} s estables (champion v$CHAMPION)"

  (
    end=$(( $(date +%s) + RUN_TIME ))
    echo "epoch,pod,cpu,memoria" > "resultados/top_${NAME}.csv"
    while [[ $(date +%s) -lt $end ]]; do
      kubectl -n "$NS" top pod -l app=api --no-headers 2>/dev/null \
        | awk -v t="$(date +%s)" '{print t","$1","$2","$3}' >> "resultados/top_${NAME}.csv"
      sleep 5
    done
  ) &
  TOP_PID=$!

  kubectl -n "$NS" exec "$POD" -c locust -- locust -f /locust/locustfile.py \
    --headless --host "$API_HOST" --users "$USERS" --spawn-rate "$SPAWN_RATE" \
    --run-time "${RUN_TIME}s" --reset-stats --csv "/tmp/$NAME" --only-summary || true
  END=$(date +%s)
  START=$(( END - STABLE_SECONDS ))
  wait "$TOP_PID" || true

  for SUFFIX in stats failures exceptions; do
    kubectl -n "$NS" cp -c locust "$POD:/tmp/${NAME}_${SUFFIX}.csv" "resultados/${NAME}_${SUFFIX}.csv" \
      >/dev/null 2>&1 || true
  done

  awk -F, -v rep="$REPLICAS" -v users="$USERS" -v sr="$SPAWN_RATE" -v maxf="$MAX_FAIL_PCT" \
    -v maxp="$MAX_P95_MS" -v champ="$CHAMPION" -v ini="$START" -v fin="$END" '
    NR == 1 { for (i = 1; i <= NF; i++) { gsub(/"/, "", $i); col[$i] = i }; next }
    { gsub(/"/, "") }
    $col["Name"] == "Aggregated" {
      n = $col["Request Count"]; f = $col["Failure Count"]
      pct = (n > 0) ? 100 * f / n : 100
      p95 = $col["95%"]
      ok = (pct < maxf && p95 < maxp) ? "si" : "no"
      printf "%s,%s,%s,%.1f,%d,%d,%.2f,%.1f,%s,%s,%s,%s,%s,%s,%s\n", rep, users, sr,
        $col["Requests/s"], n, f, pct, $col["Average Response Time"], $col["50%"], p95,
        $col["99%"], ok, champ, ini, fin
    }' "resultados/${NAME}_stats.csv" | tee -a "$SUMMARY"

  sleep "$COOLDOWN"
done

echo
column -s, -t < "$SUMMARY"
