#!/usr/bin/env bash
# Prepara el clúster ya creado en Rancher: StorageClass local-path, labels de nodos y Argo CD.
# Es idempotente. Uso (en la .106): KUBE_CONTEXT=housing ./cluster/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

CONTEXT="${KUBE_CONTEXT:-housing}"
DATA_NODE="${DATA_NODE:-nodo-data}"
SERVING_NODE="${SERVING_NODE:-nodo-serving}"

current="$(kubectl config current-context)"
if [[ "$current" != "$CONTEXT" ]]; then
  echo "El contexto actual es '$current' y se esperaba '$CONTEXT'. No se aplica nada." >&2
  exit 1
fi

echo "== Nodos"
kubectl get nodes -o wide

echo "== StorageClass local-path"
kubectl apply -f cluster/local-path-storage.yaml
kubectl -n local-path-storage rollout status deployment/local-path-provisioner --timeout=5m
kubectl patch storageclass local-path \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

echo "== Labels"
kubectl label node "$DATA_NODE" mlops/tier=data --overwrite
kubectl label node "$SERVING_NODE" mlops/tier=serving --overwrite

echo "== Argo CD"
kubectl get namespace argocd >/dev/null 2>&1 || kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f argocd/install/install.yaml
for resource in deployment/argocd-server deployment/argocd-repo-server \
                statefulset/argocd-application-controller; do
  kubectl -n argocd rollout status "$resource" --timeout=10m
done

echo "== Estado"
kubectl get nodes -L mlops/tier
kubectl get storageclass
kubectl -n argocd get pods
kubectl top nodes || echo "metrics-server todavía no responde"
