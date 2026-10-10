#!/usr/bin/env bash
# Uso: ./run_levels.sh <replicas> <usuarios> [usuarios ...]
# Ejemplo: ./run_levels.sh 1 10 30 60 100 150 200 300 400
# Corre un nivel por cada cantidad de usuarios con la misma tasa de aparicion y la misma
# ventana estable, y agrega una fila por nivel a resultados/resumen.csv con la hora (epoch)
# de inicio y fin de la ventana, para cruzarla con scripts/stats_por_nivel.sh.
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
ENCABEZADO="replicas,usuarios,rps,peticiones,fallos,fallos_pct,p50_ms,p95_ms,p99_ms,cumple,inicio_epoch,fin_epoch"
[ -f "$RESUMEN" ] || echo "$ENCABEZADO" > "$RESUMEN"
if [ "$(head -n 1 "$RESUMEN")" != "$ENCABEZADO" ]; then
  echo "$RESUMEN tiene el formato anterior (sin inicio_epoch/fin_epoch). Muevalo o borrelo y vuelva a correr."
  exit 1
fi

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
  FIN=$(date +%s)
  INICIO=$(( FIN - STABLE_SECONDS ))

  wait "$STATS_PID" || true

  awk -F, -v rep="$REPLICAS" -v users="$USERS" -v maxf="$MAX_FAIL_PCT" -v maxp="$MAX_P95_MS" \
    -v ini="$INICIO" -v fin="$FIN" '
    NR == 1 { for (i = 1; i <= NF; i++) { gsub(/"/, "", $i); col[$i] = i }; next }
    { gsub(/"/, "") }
    $col["Name"] == "Aggregated" {
      n = $col["Request Count"]; f = $col["Failure Count"]
      pct = (n > 0) ? 100 * f / n : 100
      p95 = $col["95%"]
      ok = (pct < maxf && p95 < maxp) ? "si" : "no"
      printf "%s,%s,%.1f,%d,%d,%.2f,%s,%s,%s,%s,%s,%s\n", rep, users, $col["Requests/s"], n, f, pct, $col["50%"], p95, $col["99%"], ok, ini, fin
    }' "resultados/${NAME}_stats.csv" | tee -a "$RESUMEN"

  echo "   ventana estable: $(date -d "@$INICIO" +%H:%M:%S 2>/dev/null || date -r "$INICIO" +%H:%M:%S) - $(date -d "@$FIN" +%H:%M:%S 2>/dev/null || date -r "$FIN" +%H:%M:%S)"
  echo "   CPU/memoria del generador: ../stats/locust_$NAME.csv"
  sleep "$COOLDOWN"
done

echo
column -s, -t < "$RESUMEN"
