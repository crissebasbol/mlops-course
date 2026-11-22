#!/usr/bin/env bash
# Inventario de una VM antes de montar el clúster. Uso: ./cluster/inventory.sh
set -uo pipefail

echo "== $(hostname) ($(hostname -I 2>/dev/null | awk '{print $1}'))"
grep -E '^(PRETTY_NAME)=' /etc/os-release
echo "CPU: $(nproc)"
free -h | awk 'NR<=2'
df -h / | awk 'NR<=2'
echo "Docker: $(docker --version 2>/dev/null || echo 'no instalado')"
for unit in firewalld nftables rke2-server rke2-agent rancher-system-agent; do
  printf "%-22s %s\n" "$unit" "$(systemctl is-active "$unit" 2>/dev/null)"
done
for bin in kubectl helm kind argocd rke2; do
  printf "%-8s %s\n" "$bin" "$(command -v "$bin" || echo '-')"
done
echo "Contenedores:"
docker ps -a --format '  {{.Names}}  {{.Image}}  {{.Status}}' 2>/dev/null || true
echo "Puertos 8000-8025 en uso:"
ss -ltn 2>/dev/null | awk '{print $4}' | grep -E ':80(0[0-9]|1[0-9]|2[0-5])$' || echo "  ninguno"
