#!/usr/bin/env bash
# Uso: ./scripts/stats_por_nivel.sh <stats.csv> <resumen.csv>
# Cruza las muestras de docker_stats.sh con la ventana estable de cada nivel de resumen.csv
# (columnas inicio_epoch y fin_epoch) y calcula CPU y memoria promedio y maxima por contenedor.
# OFFSET (segundos) se suma a las horas de resumen.csv si los relojes de las VMs no coinciden.
set -euo pipefail

STATS=${1:?CSV de docker_stats.sh, por ejemplo stats/rep1.csv}
RESUMEN=${2:?resumen.csv de run_levels.sh}
OFFSET=${OFFSET:-0}
SALIDA="${STATS%.csv}_por_nivel.csv"

awk -F, -v offset="$OFFSET" '
  function mib(valor,    n, u) {
    split(valor, partes, "/"); valor = partes[1]; gsub(/ /, "", valor)
    n = valor + 0; u = valor; sub(/^[0-9.]+/, "", u)
    if (u == "GiB") return n * 1024
    if (u == "KiB") return n / 1024
    if (u == "B") return n / 1048576
    return n
  }
  FNR == 1 { archivo++ }
  archivo == 1 && FNR == 1 { for (i = 1; i <= NF; i++) col[$i] = i; next }
  archivo == 1 {
    niveles++
    rep[niveles] = $col["replicas"]; usr[niveles] = $col["usuarios"]
    ini[niveles] = $col["inicio_epoch"] + offset; fin[niveles] = $col["fin_epoch"] + offset
    next
  }
  FNR == 1 { next }
  {
    t = $1; c = $3; cpu = $4; sub("%", "", cpu); mem = mib($5)
    for (n = 1; n <= niveles; n++) {
      if (t < ini[n] || t > fin[n]) continue
      k = n SUBSEP c
      if (!(k in muestras)) { orden[++total] = k }
      muestras[k]++; sum_cpu[k] += cpu; sum_mem[k] += mem
      if (cpu + 0 > max_cpu[k]) max_cpu[k] = cpu + 0
      if (mem > max_mem[k]) max_mem[k] = mem
    }
  }
  END {
    print "replicas,usuarios,contenedor,muestras,cpu_prom_pct,cpu_max_pct,mem_prom_mib,mem_max_mib"
    for (i = 1; i <= total; i++) {
      k = orden[i]; split(k, p, SUBSEP); n = p[1]
      printf "%s,%s,%s,%d,%.1f,%.1f,%.0f,%.0f\n", rep[n], usr[n], p[2], muestras[k],
        sum_cpu[k] / muestras[k], max_cpu[k], sum_mem[k] / muestras[k], max_mem[k]
    }
  }' "$RESUMEN" "$STATS" > "$SALIDA"

if [ "$(wc -l < "$SALIDA")" -le 1 ]; then
  echo "Ninguna muestra cae dentro de las ventanas de $RESUMEN. Revise que los relojes de las VMs coincidan (OFFSET)."
  exit 1
fi

column -s, -t < "$SALIDA"
echo
echo "Guardado en $SALIDA"
