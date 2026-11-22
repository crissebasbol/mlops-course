#!/usr/bin/env bash
# Borra restos de RKE2 y del agente de Rancher en un nodo (.105 o .92). Destructivo.
# Uso: sudo ./cluster/cleanup_node.sh --yes
set -euo pipefail

[[ "${1:-}" == "--yes" ]] || { echo "Borra RKE2 y todos sus datos en este nodo. Confirmar con: $0 --yes" >&2; exit 1; }
[[ $EUID -eq 0 ]] || { echo "Correr con sudo" >&2; exit 1; }

for script in /usr/local/bin/rke2-uninstall.sh /usr/bin/rke2-uninstall.sh \
              /usr/local/bin/rancher-system-agent-uninstall.sh; do
  if [[ -x "$script" ]]; then
    echo "== $script"
    "$script" || true
  fi
done

rm -rf /etc/rancher /var/lib/rancher /var/lib/kubelet /etc/cni /opt/cni /var/lib/cni
echo "Listo. Reiniciar el nodo: sudo reboot"
