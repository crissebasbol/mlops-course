# Preparar el clúster (Cristian Organista, sábado 21 o domingo 22)

No es un PR: son pasos en las VMs para que el lunes se pueda desplegar con Argo CD. Es el camino crítico del proyecto. Al final hay una lista de lo que hay que reportar al equipo.

| VM | IP | Rol |
|---|---|---|
| Instancia 1 | 10.43.97.106 | Puerta de entrada: `kubectl`, port-forwards (no es nodo) |
| Instancia 2 | 10.43.97.105 | `nodo-data`: etcd + control plane + worker (`mlops/tier=data`) |
| Instancia 3 | 10.43.97.92 | `nodo-serving`: worker (`mlops/tier=serving`) |

**Contexto:** en taller 6 se borró el contenedor de Rancher de la .106 y se creó un clúster kind (`taller6`) en la misma .106. El kubeconfig que se descargó de Rancher ya no sirve (pasaba por Rancher). El clúster RKE2 de la .105 y la .92 debería seguir vivo: se accede con el kubeconfig propio de RKE2.

## 1. Verificar que RKE2 sigue vivo

En la **.105**:

```bash
sudo systemctl status rke2-server --no-pager | head -5
sudo /var/lib/rancher/rke2/bin/kubectl --kubeconfig /etc/rancher/rke2/rke2.yaml get nodes -o wide
```

En la **.92**:

```bash
sudo systemctl status rke2-agent --no-pager | head -5
```

Los dos nodos deben estar `Ready`. Si alguno no lo está: `sudo systemctl restart rke2-server` (o `rke2-agent`) y revisar `sudo journalctl -u rke2-server -n 100`.

## 2. Acceso desde la .106 sin Rancher

Copiar el kubeconfig de RKE2 de la .105 a la .106, apuntándolo a la IP de la .105:

```bash
# en la .105
sudo cat /etc/rancher/rke2/rke2.yaml | sed 's#https://127.0.0.1:6443#https://10.43.97.105:6443#' > /tmp/housing.yaml
# copiarlo a la .106 (scp o pegando el contenido) como ~/.kube/housing.yaml y borrar /tmp/housing.yaml

# en la .106
chmod 600 ~/.kube/housing.yaml
curl -sk https://10.43.97.105:6443/version | head -3        # debe responder (401 o JSON); si no, el puerto 6443 está bloqueado
export KUBECONFIG=~/.kube/housing.yaml
kubectl config rename-context default housing
kubectl config use-context housing
kubectl get nodes -L mlops/tier
```

Agregar `export KUBECONFIG=~/.kube/housing.yaml` al `~/.bashrc` de la .106. El nombre del contexto (`housing`) es el que va en `KUBE_CONTEXT` del `.env` del proyecto.

**Nunca subir este archivo a Git:** tiene las credenciales de administrador del clúster.

## 3. Liberar recursos

Confirmar con el equipo antes de borrar: el taller 6 y el proyecto 2 ya fueron entregados.

En la **.106** (clúster kind del taller 6):

```bash
kind get clusters
kind delete cluster --name taller6
docker ps
free -h
```

En el clúster RKE2 (desde la .106):

```bash
kubectl get namespaces
helm list -A
kubectl delete namespace proyecto2      # borra Airflow, bases, MinIO, MLflow y sus volúmenes del proyecto 2
kubectl get namespaces
```

## 4. Capacidad real de los nodos

```bash
kubectl describe nodes | grep -A 6 -E "^Name:|Allocatable:"
kubectl top nodes
kubectl get storageclass
```

Y en cada VM (.105 y .92): `nproc`, `free -h`, `df -h /`.

`local-path` debe aparecer como StorageClass `(default)`. Si no está: `proyecto_2/cluster/README.md`, paso 5.

## 5. Probar la salida a internet desde los dos nodos

Argo necesita GitHub, Airflow necesita el repositorio de su chart y todos los pods necesitan DockerHub, quay.io, ghcr.io y public.ecr.aws:

```bash
for tier in data serving; do
  echo "== nodo $tier"
  kubectl run "nettest-$tier" --rm -i --restart=Never --image=curlimages/curl \
    --overrides="{\"spec\":{\"nodeSelector\":{\"mlops/tier\":\"$tier\"}}}" -- sh -c '
    for u in https://github.com https://airflow.apache.org/index.yaml https://registry-1.docker.io/v2/ \
             https://quay.io https://ghcr.io https://public.ecr.aws; do
      printf "%s " "$u"; curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 "$u"; done'
done
```

Cualquier código (200, 301, 401, 404) indica salida; `000` indica bloqueo. **Si `airflow.apache.org` da `000`, avisar de inmediato**: hay que guardar el chart de Airflow dentro del repo.

## 6. Instalar Argo CD v3.6.1

Desde la .106, en la carpeta del monorepo `mlops-course` (actualizado con `git pull`):

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f taller_6_argo/argocd/install.yaml
kubectl -n argocd rollout status deployment/argocd-server --timeout=10m
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=10m
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=10m
kubectl -n argocd get pods -o wide
```

UI en el puerto 8006 de la .106 (dejarlo corriendo en una terminal o con `nohup`):

```bash
kubectl -n argocd port-forward --address 0.0.0.0 svc/argocd-server 8006:443
```

Abrir `https://10.43.97.106:8006`. Contraseña inicial y cambio:

```bash
argocd admin initial-password -n argocd
argocd login localhost:8006 --username admin --insecure
argocd account update-password
kubectl -n argocd delete secret argocd-initial-admin-secret
```

La contraseña nueva no se escribe en ningún archivo del repo ni aparece en capturas.

## 7. Reportar al equipo

- [ ] Salida de `kubectl get nodes -L mlops/tier` (los dos nodos `Ready`).
- [ ] Nombre del contexto (`housing`).
- [ ] CPU y memoria `Allocatable` de cada nodo y `kubectl top nodes` (define los limits de Airflow y la API).
- [ ] Resultado de la prueba de red de los dos nodos.
- [ ] `kubectl -n argocd get pods` con todo en `Running`.
- [ ] Problemas encontrados y cómo se resolvieron (van a la bitácora del README).
