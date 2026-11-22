#!/usr/bin/env bash
# Prueba la salida a internet desde un pod en cada nodo. Cualquier código HTTP indica salida; 000, bloqueo.
# Uso (en la .106): ./cluster/nettest.sh
set -uo pipefail

URLS="https://github.com https://airflow.apache.org/index.yaml https://registry-1.docker.io/v2/ \
https://quay.io https://ghcr.io https://public.ecr.aws https://pypi.org/simple/"

for tier in data serving; do
  echo "== nodo mlops/tier=$tier"
  kubectl run "nettest-$tier" --rm -i --restart=Never --quiet --image=curlimages/curl:8.11.1 \
    --overrides="{\"spec\":{\"nodeSelector\":{\"mlops/tier\":\"$tier\"}}}" -- sh -c "
      for u in $URLS; do
        printf '%-45s %s\n' \"\$u\" \"\$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \"\$u\")\"
      done"
done
