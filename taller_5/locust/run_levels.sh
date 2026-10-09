#!/usr/bin/env bash
# Uso: ./run_levels.sh <replicas> <usuarios> [usuarios ...]
# Ejemplo: ./run_levels.sh 1 50 100 200 400
# Corre un nivel por cada cantidad de usuarios con la misma tasa de aparicion y la misma
# ventana estable, y agrega una fila por nivel a resultados/resumen.csv.
set -euo pipefail
cd "$(dirname "$0")"

REPLICAS=${1:?numero de replicas de la API (1 o 3)}
shift
[ $# -gt 0 ] || { echo "Indique al menos un nivel de usuarios"; exit 1; }

API_HOST=${API_HOST:-http://10.43.97.105:8000}
SPAWN_RATE=${SPAWN_RATE:-20}
STABLE_SECONDS=${STABLE_SECONDS:-120}
COOLDOWN=${COOLDOWN:-30}
PROCESSES=${LOCUST_PROCESSES:-1}
MAX_FAIL_PCT=${MAX_FAIL_PCT:-1}
MAX_P95_MS=${MAX_P95_MS:-500}

RESUMEN=resultados/resumen.csv
[ -f "$RESUMEN" ] || echo "replicas,usuarios,rps,peticiones,fallos,fallos_pct,p50_ms,p95_ms,p99_ms,cumple" > "$RESUMEN"

docker compose build locust

for USERS in "$@"; do
  RAMP=$(( (USERS + SPAWN_RATE - 1) / SPAWN_RATE ))
  RUN_TIME=$(( RAMP + STABLE_SECONDS ))
  NAME="rep${REPLICAS}_u${USERS}"
  echo "== $NAME: $USERS usuarios, spawn-rate $SPAWN_RATE, ${RAMP}s de rampa + ${STABLE_SECONDS}s estables"

  ../scripts/docker_stats.sh "locust_$NAME" "$RUN_TIME" locust > /dev/null &
  STATS_PID=$!

  docker compose run --rm --no-deps locust \
    --headless \
    --host "$API_HOST" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "${RUN_TIME}s" \
    --reset-stats \
    --processes "$PROCESSES" \
    --csv "/resultados/$NAME" \
    --only-summary || true

  wait "$STATS_PID" || true

  awk -F, -v rep="$REPLICAS" -v users="$USERS" -v maxf="$MAX_FAIL_PCT" -v maxp="$MAX_P95_MS" '
    NR == 1 { for (i = 1; i <= NF; i++) { gsub(/"/, "", $i); col[$i] = i }; next }
    { gsub(/"/, "") }
    $col["Name"] == "Aggregated" {
      n = $col["Request Count"]; f = $col["Failure Count"]
      pct = (n > 0) ? 100 * f / n : 100
      p95 = $col["95%"]
      ok = (pct < maxf && p95 < maxp) ? "si" : "no"
      printf "%s,%s,%.1f,%d,%d,%.2f,%s,%s,%s,%s\n", rep, users, $col["Requests/s"], n, f, pct, $col["50%"], p95, $col["99%"], ok
    }' "resultados/${NAME}_stats.csv" | tee -a "$RESUMEN"

  echo "   CPU/memoria del generador: ../stats/locust_$NAME.csv"
  sleep "$COOLDOWN"
done

echo
column -s, -t < "$RESUMEN"
