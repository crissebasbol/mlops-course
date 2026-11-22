#!/usr/bin/env bash
# Prepara un nodo antes de registrarlo en Rancher.
# Uso: sudo ./cluster/prepare_node.sh nodo-data      (en la .105)
#      sudo ./cluster/prepare_node.sh nodo-serving   (en la .92)
set -euo pipefail

name="${1:-}"
[[ "$name" == "nodo-data" || "$name" == "nodo-serving" ]] || {
  echo "Uso: $0 <nodo-data|nodo-serving>" >&2
  exit 1
}
[[ $EUID -eq 0 ]] || { echo "Correr con sudo" >&2; exit 1; }

hostnamectl set-hostname "$name"

if systemctl is-active --quiet firewalld; then
  systemctl disable --now firewalld
fi
systemctl enable --now nftables

cat > /etc/sysctl.d/99-housing-mlops.conf <<'EOF'
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512
EOF
sysctl --system >/dev/null

echo "hostname: $(hostname)"
echo "firewalld: $(systemctl is-active firewalld 2>/dev/null)"
echo "nftables: $(systemctl is-active nftables)"
