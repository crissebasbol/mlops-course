#!/usr/bin/env bash
# Uso: ./taller_6_argo/scripts/limpiar_106.sh
# Baja en 10.43.97.106 lo de talleres anteriores: Locust de taller_5 y port-forwards de proyecto_2.
# Rancher se borra aparte (ver README, paso 1).
set -uo pipefail
cd "$(dirname "$0")/../.."

echo "== taller_5: Locust"
docker compose -f taller_5/locust/docker-compose.yml down || true

echo "== proyecto_2: port-forwards"
./proyecto_2/scripts/port_forward.sh stop || true

echo "== Estado"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
ss -ltnp 2>/dev/null | grep -E ':80(0[0-9]|1[0-9]|2[0-5])\b' || echo "Sin procesos escuchando en 8000-8025"
nproc
free -h
df -h /
