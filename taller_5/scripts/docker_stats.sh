#!/usr/bin/env bash
# Uso: ./scripts/docker_stats.sh <nombre> <segundos> [filtro]
# Guarda docker stats cada 2 s en stats/<nombre>.csv y al final imprime el pico por contenedor.
set -euo pipefail

NOMBRE=${1:?nombre del archivo, por ejemplo rep1_u200}
SEGUNDOS=${2:?duracion en segundos}
FILTRO=${3:-taller5}

DIR="$(cd "$(dirname "$0")/.." && pwd)/stats"
mkdir -p "$DIR"
SALIDA="$DIR/$NOMBRE.csv"

echo "timestamp,container,cpu_pct,mem_usage,mem_pct" > "$SALIDA"
FIN=$(( $(date +%s) + SEGUNDOS ))
while [ "$(date +%s)" -lt "$FIN" ]; do
  docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}' \
    | grep "$FILTRO" \
    | sed "s/^/$(date +%H:%M:%S),/" >> "$SALIDA" || true
  sleep 2
done

echo "Pico por contenedor ($SALIDA):"
awk -F, 'NR > 1 {
  cpu = $3; sub("%", "", cpu); mem = $5; sub("%", "", mem)
  if (cpu + 0 > max_cpu[$2]) max_cpu[$2] = cpu + 0
  if (mem + 0 > max_mem[$2]) { max_mem[$2] = mem + 0; uso[$2] = $4 }
} END {
  printf "%-32s %8s %8s  %s\n", "contenedor", "cpu_max", "mem_max", "mem_uso"
  for (c in max_cpu) printf "%-32s %7.1f%% %7.1f%%  %s\n", c, max_cpu[c], max_mem[c], uso[c]
}' "$SALIDA" | sort
