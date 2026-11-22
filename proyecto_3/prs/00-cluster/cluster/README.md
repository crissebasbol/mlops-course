# Clúster de Kubernetes (Rancher + RKE2)

Cómo se monta desde cero el clúster donde corre el proyecto. Todo lo que se puede automatizar está en scripts idempotentes de esta carpeta; lo único manual es la creación del clúster en la interfaz de Rancher (paso 4).

| VM | IP | Hostname | Rol |
|---|---|---|---|
| Instancia 1 | 10.43.97.106 | - | Rancher, `kubectl`, `helm`, port-forwards (no es nodo) |
| Instancia 2 | 10.43.97.105 | `nodo-data` | etcd + control plane + worker, `mlops/tier=data`: bases de datos, MinIO, MLflow, Airflow, API de datos, Locust |
| Instancia 3 | 10.43.97.92 | `nodo-serving` | worker, `mlops/tier=serving`: API de inferencia, Streamlit, Prometheus, Grafana |

Solo los puertos 8000-8025 de las VMs están abiertos hacia afuera: las UIs se publican con port-forward desde la .106 (`scripts/port_forward.sh`).

| Puerto | Servicio | Puerto | Servicio |
|---|---|---|---|
| 8001 | Rancher | 8007 | Streamlit |
| 8002 | Airflow | 8008 | Grafana |
| 8003 | MLflow | 8009 | Prometheus |
| 8004 | Consola de MinIO | 8010 | Locust |
| 8005 | API de inferencia | 8011 | API de datos |
| 8006 | Argo CD | | |

## Scripts

| Script | Dónde | Qué hace |
|---|---|---|
| `inventory.sh` | Las tres VMs | Sistema, CPU, memoria, disco, servicios, binarios, contenedores y puertos en uso |
| `cleanup_node.sh --yes` | .105 y .92, solo si quedó algo | Desinstala RKE2 y el agente de Rancher y borra sus datos |
| `install_rancher.sh` | .106 | Módulos del kernel (la primera vez pide reiniciar) y Rancher en el puerto 8001 |
| `prepare_node.sh <nombre>` | .105 y .92 | Hostname, firewalld apagado, nftables encendido, límites de inotify |
| `bootstrap.sh` | .106 | StorageClass `local-path` por defecto, labels `mlops/tier` y Argo CD v3.6.1 |
| `nettest.sh` | .106 | Prueba la salida a internet desde un pod en cada nodo |
| `../scripts/create_secrets.sh` | .106 | Namespace `housing-mlops` y Secrets desde un `.env` local |
| `../scripts/port_forward.sh` | .106 | Publica las UIs en los puertos 80xx |

`local-path-storage.yaml` (v0.0.32) y `../argocd/install/install.yaml` (Argo CD v3.6.1) están guardados en el repo porque la red de la universidad bloquea `raw.githubusercontent.com`. Al de `local-path` se le agregaron `requests`/`limits` y se fijó la versión de `busybox`; no tiene probes porque el provisionador no expone un endpoint de salud.

## Pasos

### 1. Clonar el repo en las tres VMs

```bash
git clone https://github.com/crissebasbol/housing-price-mlops.git ~/housing-price-mlops
cd ~/housing-price-mlops
./cluster/inventory.sh
```

Si el inventario muestra restos de RKE2 o de Rancher en la .105 o la .92: `sudo ./cluster/cleanup_node.sh --yes && sudo reboot`.

### 2. Rancher en la .106

```bash
./cluster/install_rancher.sh     # la primera vez: sudo reboot y volver a correrlo
```

Abrir `https://10.43.97.106:8001`, entrar con la contraseña inicial que imprime el script, cambiarla y poner como **Server URL** `https://10.43.97.106:8001`.

### 3. Preparar los nodos

```bash
sudo ./cluster/prepare_node.sh nodo-data       # en la .105
sudo ./cluster/prepare_node.sh nodo-serving    # en la .92
```

### 4. Crear el clúster en Rancher (manual)

1. **Cluster Management > Create > Custom**, nombre `housing`, RKE2 con la versión de Kubernetes por defecto, **Create**.
2. En **Registration**, marcar **Insecure** (Rancher usa un certificado autofirmado).
3. En la .105: roles **etcd + Control Plane + Worker**; copiar el comando y ejecutarlo.
4. En la .92: solo **Worker**; copiar el comando y ejecutarlo.
5. Esperar a que el clúster quede **Active** (avance: `sudo journalctl -u rancher-system-agent -f` en cada nodo).

### 5. `kubectl` y `helm` en la .106

Si no están instalados:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl
curl -fsSL https://get.helm.sh/helm-v3.18.4-linux-amd64.tar.gz | tar xz
sudo install -o root -g root -m 0755 linux-amd64/helm /usr/local/bin/helm && rm -rf linux-amd64
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/download/v3.6.1/argocd-linux-amd64
sudo install -m 0555 argocd /usr/local/bin/argocd && rm argocd
```

En Rancher, clúster `housing` > **Download KubeConfig**; pegarlo en `~/.kube/config` de la .106 (`chmod 600`). El contexto se llama `housing`. **Ese archivo nunca va a Git.**

### 6. Bootstrap del clúster

```bash
KUBE_CONTEXT=housing ./cluster/bootstrap.sh
./cluster/nettest.sh
```

Si en `nettest.sh` aparece `000` para `airflow.apache.org`, el chart de Airflow hay que guardarlo dentro del repo.

Si `firewalld` está activo en la .106: `sudo firewall-cmd --permanent --add-port=8001-8011/tcp && sudo firewall-cmd --reload`.

### 7. Argo CD

```bash
./scripts/port_forward.sh start
argocd admin initial-password -n argocd
argocd login localhost:8006 --username admin --insecure
argocd account update-password
kubectl -n argocd delete secret argocd-initial-admin-secret
```

UI en `https://10.43.97.106:8006`. Las contraseñas no se escriben en el repo ni aparecen en capturas.

### 8. Secrets del proyecto

```bash
cp .env.example .env && chmod 600 .env
```

Completar `KUBE_CONTEXT=housing` y cada contraseña con un valor aleatorio hexadecimal (`openssl rand -hex 16`), para que no haya caracteres que rompan las URIs. **El `.env` nunca se sube a Git.**

```bash
bash scripts/create_secrets.sh
kubectl -n housing-mlops get secrets
```

Se vuelve a correr cada vez que un componente nuevo agrega su Secret (es idempotente).
