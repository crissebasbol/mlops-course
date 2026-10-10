#!/usr/bin/env bash
# Uso: ./scripts/docker_stats.sh <nombre> [segundos] [filtro]
# Guarda docker stats cada 2 s en stats/<nombre>.csv. Sin segundos (o con 0) corre hasta Ctrl+C.
# Al terminar imprime el pico por contenedor.
set -euo pipefail

NOMBRE=${1:?nombre del archivo, por ejemplo rep1}
SEGUNDOS=${2:-0}
FILTRO=${3:-taller5}

DIR="$(cd "$(dirname "$0")/.." && pwd)/stats"
mkdir -p "$DIR"
SALIDA="$DIR/$NOMBRE.csv"

PARAR=
trap 'PARAR=1' INT TERM

echo "epoch,hora,container,cpu_pct,mem_usage,mem_pct" > "$SALIDA"
FIN=$(( $(date +%s) + SEGUNDOS ))
[ "$SEGUNDOS" -gt 0 ] || echo "Registrando en $SALIDA hasta Ctrl+C..."
while [ -z "$PARAR" ] && { [ "$SEGUNDOS" -eq 0 ] || [ "$(date +%s)" -lt "$FIN" ]; }; do
  MUESTRA=$(docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}' | grep "$FILTRO" || true)
  [ -n "$MUESTRA" ] && echo "$MUESTRA" | sed "s/^/$(date +%s),$(date +%H:%M:%S),/" >> "$SALIDA"
  sleep 2 || true
done

echo "Pico por contenedor ($SALIDA):"
awk -F, 'NR > 1 {
  cpu = $4; sub("%", "", cpu); mem = $6; sub("%", "", mem)
  if (cpu + 0 > max_cpu[$3]) max_cpu[$3] = cpu + 0
  if (mem + 0 > max_mem[$3]) { max_mem[$3] = mem + 0; uso[$3] = $5 }
} END {
  printf "%-32s %8s %8s  %s\n", "contenedor", "cpu_max", "mem_max", "mem_uso"
  for (c in max_cpu) printf "%-32s %7.1f%% %7.1f%%  %s\n", c, max_cpu[c], max_mem[c], uso[c]
}' "$SALIDA" | sort
