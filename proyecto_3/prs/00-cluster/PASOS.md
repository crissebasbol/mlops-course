# 00. Montar el clúster desde cero (Cristian Organista)

No es un PR: son los pasos en las VMs para tener el clúster listo antes de desplegar el PR 7a. Es el camino crítico del proyecto. Las VMs se limpiaron el 21 nov, así que se arma todo desde cero, igual que en proyecto_2: **Rancher en la .106 y un clúster RKE2 con la .105 y la .92**.

| VM | IP | Hostname | Rol |
|---|---|---|---|
| Instancia 1 | 10.43.97.106 | - | Rancher, `kubectl`, `helm`, port-forwards (no es nodo) |
| Instancia 2 | 10.43.97.105 | `nodo-data` | etcd + control plane + worker, `mlops/tier=data`: bases, MinIO, MLflow, Airflow, API de datos, Locust |
| Instancia 3 | 10.43.97.92 | `nodo-serving` | worker, `mlops/tier=serving`: API de inferencia, Streamlit, Prometheus, Grafana |

Puertos públicos en la .106 (solo 8000-8025 están abiertos hacia afuera): 8001 Rancher, 8002 Airflow, 8003 MLflow, 8004 consola MinIO, 8005 API, 8006 Argo CD, 8007 Streamlit, 8008 Grafana, 8009 Prometheus, 8010 Locust, 8011 API de datos.

**Capturas para el README** (sin contraseñas ni tokens visibles): clúster `Active` en Rancher (paso 4), `kubectl get nodes` (paso 6), Argo CD con sus pods `Running` (paso 9).

## 0. Inventario (las tres VMs)

```bash
hostname; cat /etc/os-release | head -2
nproc; free -h; df -h /
docker --version 2>/dev/null || echo "sin docker"
sudo systemctl is-active firewalld nftables 2>/dev/null
ls /usr/local/bin | grep -E "rke2|rancher|kubectl|helm|kind" || echo "sin binarios de kubernetes"
```

Anotar CPU, RAM y disco de cada VM: definen los límites de Airflow y de la API.

## 1. Limpiar restos (solo si el paso 0 mostró algo)

En la .105 y la .92, si quedó algo de RKE2 o del agente de Rancher:

```bash
sudo /usr/local/bin/rke2-uninstall.sh 2>/dev/null || sudo /usr/bin/rke2-uninstall.sh 2>/dev/null || true
sudo /usr/local/bin/rancher-system-agent-uninstall.sh 2>/dev/null || true
sudo rm -rf /etc/rancher /var/lib/rancher /var/lib/kubelet /etc/cni /opt/cni /var/lib/cni
sudo reboot
```

En la .106, si quedaron contenedores o el clúster kind del taller 6:

```bash
kind delete cluster --name taller6 2>/dev/null || true
docker ps -a
docker rm -f rancher 2>/dev/null || true
docker volume prune -f
```

## 2. Rancher en la .106

Módulos del kernel que Rancher necesita (una sola vez, luego reiniciar):

```bash
sudo tee /etc/modules-load.d/rancher.conf <<'EOF'
ip_tables
ip_conntrack
iptable_filter
ipt_state
EOF
sudo reboot
```

Rancher en el puerto 8001:

```bash
docker run -d --name=rancher --privileged --restart=unless-stopped \
  -p 8001:443 rancher/rancher:latest
docker logs rancher 2>&1 | grep "Bootstrap Password:"
```

Abrir `https://10.43.97.106:8001`, cambiar la contraseña de `admin` (no escribirla en ningún archivo del repo) y poner como **Server URL** `https://10.43.97.106:8001` (con el puerto, para que los nodos se registren por ahí).

## 3. Preparar la .105 y la .92

```bash
sudo hostnamectl set-hostname nodo-data      # en la .105
sudo hostnamectl set-hostname nodo-serving   # en la .92

sudo systemctl stop firewalld && sudo systemctl disable firewalld
sudo systemctl enable --now nftables
```

## 4. Crear el clúster `housing` en Rancher

1. **Cluster Management > Create > Custom**, nombre `housing`, RKE2 con la versión de Kubernetes por defecto, **Create**.
2. En **Registration** marcar **Insecure** (Rancher tiene certificado autofirmado).
3. En la **.105**: roles **etcd + Control Plane + Worker**, copiar el comando y ejecutarlo.
4. En la **.92**: solo **Worker**, copiar el comando y ejecutarlo.
5. Esperar a que el clúster quede **Active** (avance: `sudo journalctl -u rancher-system-agent -f` en cada nodo). Toma de 5 a 15 minutos.

## 5. `kubectl` y `helm` en la .106

Si no están instalados:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl
curl -fsSL https://get.helm.sh/helm-v3.18.4-linux-amd64.tar.gz | tar xz
sudo install -o root -g root -m 0755 linux-amd64/helm /usr/local/bin/helm && rm -rf linux-amd64
```

Kubeconfig: en Rancher, clúster `housing` > **Download KubeConfig**, y pegarlo en la .106:

```bash
mkdir -p ~/.kube
vim ~/.kube/config      # pegar el contenido descargado
chmod 600 ~/.kube/config
kubectl config get-contexts      # el contexto se llama housing
kubectl config use-context housing
kubectl get nodes -o wide
```

**Este archivo nunca va a Git**: tiene credenciales del clúster.

## 6. StorageClass por defecto y labels

RKE2 no trae provisionador de volúmenes. Se usa `local-path-provisioner` v0.0.32, guardado en el monorepo porque la red de la universidad bloquea `raw.githubusercontent.com`:

```bash
git clone git@github.com:crissebasbol/mlops-course.git ~/mlops-course   # o git pull si ya está
kubectl apply -f ~/mlops-course/proyecto_2/cluster/local-path-storage.yaml
kubectl -n local-path-storage rollout status deployment/local-path-provisioner
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
kubectl get storageclass

kubectl label node nodo-data mlops/tier=data
kubectl label node nodo-serving mlops/tier=serving
kubectl get nodes -L mlops/tier
```

Validación (metrics-server viene con RKE2):

```bash
kubectl top nodes
kubectl describe nodes | grep -A 6 -E "^Name:|Allocatable:"
```

## 7. Probar la salida a internet desde los dos nodos

Argo necesita GitHub, Airflow necesita el repositorio de su chart y todos los pods necesitan bajar imágenes:

```bash
for tier in data serving; do
  echo "== nodo $tier"
  kubectl run "nettest-$tier" --rm -i --restart=Never --image=curlimages/curl \
    --overrides="{\"spec\":{\"nodeSelector\":{\"mlops/tier\":\"$tier\"}}}" -- sh -c '
    for u in https://github.com https://airflow.apache.org/index.yaml https://registry-1.docker.io/v2/ \
             https://quay.io https://ghcr.io https://public.ecr.aws https://pypi.org/simple/; do
      printf "%s " "$u"; curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 "$u"; done'
done
```

Cualquier código (200, 301, 401, 404) indica salida; `000` indica bloqueo. **Si `airflow.apache.org` da `000`, avisar de inmediato**: hay que guardar el chart de Airflow dentro del repo.

## 8. Firewall de la .106

Si `firewalld` está activo en la .106, abrir los puertos de las UIs:

```bash
sudo firewall-cmd --permanent --add-port=8001-8011/tcp && sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

## 9. Argo CD v3.6.1

Con el `install.yaml` guardado en el monorepo (taller 6):

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f ~/mlops-course/taller_6_argo/argocd/install.yaml
kubectl -n argocd rollout status deployment/argocd-server --timeout=10m
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=10m
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=10m
kubectl -n argocd get pods -o wide
```

`--server-side` es necesario: el CRD de `ApplicationSet` es demasiado grande para un `apply` normal.

CLI de Argo (si no está en la .106):

```bash
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/download/v3.6.1/argocd-linux-amd64
sudo install -m 0555 argocd /usr/local/bin/argocd && rm argocd
```

UI en el puerto 8006 (dejarlo corriendo con `nohup` o en una terminal aparte):

```bash
nohup kubectl -n argocd port-forward --address 0.0.0.0 svc/argocd-server 8006:443 > ~/pf-argocd.log 2>&1 &
argocd admin initial-password -n argocd
argocd login localhost:8006 --username admin --insecure
argocd account update-password
kubectl -n argocd delete secret argocd-initial-admin-secret
```

Abrir `https://10.43.97.106:8006`. La contraseña nueva no se escribe en ningún archivo del repo ni aparece en capturas.

## 10. Namespace y Secrets del proyecto

En la .106, con el repo del proyecto:

```bash
git clone git@github.com:crissebasbol/housing-price-mlops.git ~/housing-price-mlops   # o git pull
cd ~/housing-price-mlops
cp .env.example .env
chmod 600 .env
```

Completar `.env`: `KUBE_CONTEXT=housing` y cada contraseña con un valor aleatorio, por ejemplo `openssl rand -hex 16` (hexadecimal para que no haya caracteres que rompan URIs). `MINIO_ROOT_USER` puede ser `minioadmin`. **El `.env` nunca se sube a Git** (está en `.gitignore`).

Cuando el PR 7a esté fusionado (`git pull` antes):

```bash
bash scripts/create_secrets.sh
kubectl -n housing-mlops get secrets
```

Crea el namespace `housing-mlops` y los Secrets de la base de datos, MinIO y MLflow. Se vuelve a correr cuando lleguen los de Airflow, la API y Grafana (es idempotente).

## 11. Reportar al equipo

- [ ] Inventario del paso 0 (CPU, RAM y disco de cada VM).
- [ ] `kubectl get nodes -L mlops/tier` con los dos nodos `Ready`.
- [ ] `Allocatable` de cada nodo y `kubectl top nodes`.
- [ ] Resultado de la prueba de red de los dos nodos.
- [ ] `kubectl -n argocd get pods` con todo en `Running`.
- [ ] `kubectl -n housing-mlops get secrets` (solo los nombres).
- [ ] Problemas encontrados y cómo se resolvieron (van a la bitácora del README).
