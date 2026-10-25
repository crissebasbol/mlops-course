# Clúster de Kubernetes (Rancher + RKE2)

Pasos para preparar las tres VMs.

| VM | IP | Rol |
|---|---|---|
| Instancia 1 (Fabián) | 10.43.97.106 | Rancher (no es nodo), `kubectl`, `helm`, port-forwards |
| Instancia 2 (Cristian Organista) | 10.43.97.105 | Nodo `etcd + control plane + worker`, label `mlops/tier=data` |
| Instancia 3 (Cristhian Bolaños) | 10.43.97.92 | Nodo `worker`, label `mlops/tier=serving` |

## 1. Rancher en 10.43.97.106

Módulos del kernel:

```bash
sudo tee /etc/modules-load.d/rancher.conf <<'EOF'
ip_tables
ip_conntrack
iptable_filter
ipt_state
EOF
sudo reboot
```

Rancher publicado en el puerto **8001**:

```bash
docker run -d --name=rancher --privileged --restart=unless-stopped \
  -p 8001:443 rancher/rancher:latest

docker logs rancher 2>&1 | grep "Bootstrap Password:"
```

Abrir `https://10.43.97.106:8001`, cambiar la contraseña de `admin` y poner como
**Server URL** `https://10.43.97.106:8001` (con el puerto, para que los nodos se
registren por ahí).

## 2. Preparar 10.43.97.105 y 10.43.97.92

```bash
sudo hostnamectl set-hostname nodo-data      # en .105
sudo hostnamectl set-hostname nodo-serving   # en .92

sudo systemctl stop firewalld && sudo systemctl disable firewalld
sudo systemctl enable --now nftables
```

## 3. Crear el clúster `mlops`

1. Rancher > **Cluster Management > Create > Custom**, nombre `mlops`, RKE2 por defecto, **Create**.
2. En **Registration** marcar **Insecure** (certificado autofirmado).
3. En `10.43.97.105`: roles **etcd + Control Plane + Worker**, copiar el comando y ejecutarlo.
4. En `10.43.97.92`: solo **Worker**, copiar el comando y ejecutarlo.
5. Esperar a que el clúster quede **Active** (`sudo journalctl -u rancher-system-agent -f` para ver el avance).

## 4. kubectl y helm en 10.43.97.106

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

mkdir -p ~/.kube
vim ~/.kube/config        # pegar el KubeConfig del clúster mlops (Download KubeConfig)
chmod 600 ~/.kube/config
kubectl get nodes -o wide
```

## 5. StorageClass por defecto y labels

RKE2 no trae provisionador de volúmenes. Se usa `local-path-provisioner` de Rancher:

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.32/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
kubectl get storageclass
```

Labels que usan los `nodeSelector` de los manifiestos (usar los nombres que muestre `kubectl get nodes`):

```bash
kubectl label node nodo-data mlops/tier=data
kubectl label node nodo-serving mlops/tier=serving
kubectl get nodes -L mlops/tier
```

## 6. Validación

```bash
kubectl top nodes                       # metrics-server viene con RKE2
kubectl create deployment hola --image=nginx
kubectl get pods -o wide -w
kubectl delete deployment hola
```

## 7. Firewall en 10.43.97.106

Si `firewalld` está activo en la VM de Rancher, abrir los puertos de los port-forwards:

```bash
sudo firewall-cmd --permanent --add-port=8001-8010/tcp
sudo firewall-cmd --reload
```

Con esto el clúster queda listo para `scripts/deploy.sh` (ver el README principal).
