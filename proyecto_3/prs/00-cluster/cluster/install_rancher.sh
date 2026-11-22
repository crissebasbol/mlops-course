#!/usr/bin/env bash
# Rancher en la VM de entrada (.106), publicado en el puerto 8001.
# Uso: ./cluster/install_rancher.sh   (la primera vez configura módulos del kernel y pide reiniciar)
set -euo pipefail

RANCHER_IMAGE="${RANCHER_IMAGE:-rancher/rancher:latest}"
RANCHER_PORT="${RANCHER_PORT:-8001}"
MODULES_FILE=/etc/modules-load.d/rancher.conf

if [[ ! -f "$MODULES_FILE" ]]; then
  printf 'ip_tables\nip_conntrack\niptable_filter\nipt_state\n' | sudo tee "$MODULES_FILE" >/dev/null
  echo "Módulos del kernel configurados en $MODULES_FILE."
  echo "Reiniciar la VM (sudo reboot) y volver a correr este script."
  exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -qx rancher; then
  echo "El contenedor rancher ya existe"
  docker start rancher >/dev/null
else
  docker run -d --name=rancher --privileged --restart=unless-stopped \
    -p "${RANCHER_PORT}:443" "$RANCHER_IMAGE" >/dev/null
fi

echo "Esperando a Rancher..."
password=""
for _ in $(seq 1 60); do
  password="$(docker logs rancher 2>&1 | sed -n 's/.*Bootstrap Password: //p' | tail -1)"
  [[ -n "$password" ]] && break
  sleep 5
done

ip="$(hostname -I | awk '{print $1}')"
echo "Abrir https://${ip}:${RANCHER_PORT}"
if [[ -n "$password" ]]; then
  echo "Contraseña inicial de admin: $password (cambiarla al entrar; no copiarla en ningún archivo)"
else
  echo "Rancher aún no imprime la contraseña: docker logs rancher 2>&1 | grep 'Bootstrap Password'"
fi
echo "Server URL en Rancher: https://${ip}:${RANCHER_PORT} (con el puerto)"
