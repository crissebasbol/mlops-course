# Taller 6 - Despliegue continuo con Argo CD

Guía para agregar **CD con GitOps** al taller 6. Todo corre en **`10.43.97.106`**: un clúster
**kind** de un solo nodo sobre el Docker de la VM, con Argo CD y la API adentro. Los comandos se
ejecutan en la 106 desde la raíz del repositorio.

```text
10.43.97.106
└── Docker
    └── kind-taller6 (1 nodo, Kubernetes)
        ├── namespace argocd    Argo CD v3.6.1  <- port-forward 8006
        └── namespace taller6   API taller6-housing (2 réplicas)  <- port-forward 8005
```

## Objetivo

1. **CI** (ya existe, `.github/workflows/taller6-ci-cd.yml`): pruebas con cobertura del 90 % y publicación
   de `crissebasbol/taller6-housing` en Docker Hub con tags `latest` y SHA.
2. **CD** (nuevo): Argo CD vigila `taller_6_argo/k8s` en la rama `master` y lo aplica en el clúster.
   Desplegar = hacer commit en Git; Argo detecta el cambio y sincroniza.

```text
PR -> GitHub Actions (pytest) -> merge -> imagen :<sha> en Docker Hub
   -> el job update-manifest escribe el tag en taller_6_argo/k8s/kustomization.yaml (commit)
   -> Argo CD ve el commit -> sync -> nuevo Deployment en el clúster
```

Argo CD hace *pull* desde GitHub: GitHub no necesita llegar a la VM, es Argo quien consulta el
repositorio (cada 3 minutos por defecto).

## Conceptos de Argo CD

| Concepto | Qué es |
|---|---|
| **Application** | Recurso (CRD) que une un origen en Git (`repoURL`, `targetRevision`, `path`) con un destino (clúster + namespace) |
| **Target state** | Lo que dice Git |
| **Live state** | Lo que hay en el clúster |
| **Sync status** | `Synced` si son iguales, `OutOfSync` si difieren |
| **Health** | `Healthy`, `Progressing`, `Degraded`, según el estado de los recursos (pods listos, probes) |
| **Auto-sync** | Aplica solo cada commit nuevo, sin pulsar *Sync* |
| **Prune** | Borra del clúster lo que se borró de Git |
| **Self-heal** | Si alguien cambia algo a mano con `kubectl`, Argo lo devuelve a lo que dice Git |
| **Rollback** | Volver a un commit anterior (`git revert` o `argocd app rollback`) |

## Archivos

```text
taller_6_argo/
├── README.md
├── kind-config.yaml          clúster kind "taller6" de un nodo
├── argocd/
│   ├── install.yaml          Argo CD v3.6.1 (la red de la universidad bloquea raw.githubusercontent.com)
│   └── application.yaml      Application taller6-housing -> taller_6_argo/k8s en master
├── k8s/
│   ├── namespace.yaml        namespace taller6
│   ├── deployment.yaml       2 réplicas, uvicorn app:app, probes en /health
│   ├── service.yaml          ClusterIP, puerto 8000
│   └── kustomization.yaml    namespace, labels y tag de la imagen (images.newTag)
└── scripts/
    ├── limpiar_106.sh        baja taller_5 y los port-forwards de proyecto_2, muestra recursos libres
    └── port_forward.sh       UI de Argo CD (8006) y API (8005), contexto kind-taller6
```

La app no se copia: se usa la misma imagen que publica el CI de `taller_6/unit_testing`. El tag
inicial es `6ddd6d6e5660e01d468ae97be9df72ed5bd3165f`, el SHA del último merge publicado en Docker Hub.

| Servicio | URL |
|---|---|
| UI de Argo CD | `https://10.43.97.106:8006` |
| API taller 6 (Swagger) | `http://10.43.97.106:8005/docs` |

### Recursos necesarios en la 106

| Componente | RAM | CPU |
|---|---|---|
| Nodo kind (Kubernetes) | ~0.6 a 1 GB | ~0.5 |
| Argo CD (7 pods) | ~1 a 1.5 GB | ~0.5 |
| API taller 6 (2 réplicas) | ~256 MB | ~0.2 |
| **Total** | **~2.5 a 3 GB** | **~1 a 1.5** |

Mínimo 2 vCPU, 4 GB de RAM libres y ~15 GB de disco libre (lo ideal son 8 GB de RAM).

---

## Paso 0. Preparar el repo en la 106

Argo lee la rama `master` de GitHub, así que esta carpeta debe estar mergeada antes del paso 7.

```bash
ssh <usuario>@10.43.97.106
cd mlops-course
git checkout master && git pull
```

## Paso 1. Limpiar la 106

### 1.1 Talleres anteriores

```bash
./taller_6_argo/scripts/limpiar_106.sh
```

| Qué baja | Cómo |
|---|---|
| Locust de `taller_5` (puerto 8006) | `docker compose -f taller_5/locust/docker-compose.yml down` |
| Port-forwards de `proyecto_2` (8002-8010) | `./proyecto_2/scripts/port_forward.sh stop` |

Al final muestra `docker ps`, los puertos `8000-8025` en uso, `nproc`, `free -h` y `df -h /` para
confirmar que la 106 tiene los recursos de la tabla anterior.

### 1.2 Rancher

Rancher (contenedor `rancher`, puerto 8001) consume 2 a 4 GB de RAM. El clúster de la 105 y la 92 sigue
corriendo sin Rancher, pero ya no se puede administrar desde su UI ni con el kubeconfig descargado de
Rancher, así que se guarda una copia antes de borrarlo:

```bash
cp ~/.kube/config ~/.kube/config.rancher 2>/dev/null || true
docker rm -f rancher
docker ps
free -h
```

## Paso 2. Crear el clúster kind

Binarios (Linux amd64). Si GitHub Releases está bloqueado, se descargan los mismos archivos en otro
equipo y se copian con `scp <archivo> <usuario>@10.43.97.106:~/`.

```bash
curl -Lo kind https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64
sudo install -m 0755 kind /usr/local/bin/kind && rm kind
kind version

curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/download/v3.6.1/argocd-linux-amd64
sudo install -m 0555 argocd /usr/local/bin/argocd && rm argocd
argocd version --client
```

Crear el clúster (descarga `kindest/node` de Docker Hub) y verificar:

```bash
kind create cluster --config taller_6_argo/kind-config.yaml
kubectl config use-context kind-taller6
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
kubectl -n kube-system get pods
```

`kind create cluster` agrega el contexto `kind-taller6` al kubeconfig y lo deja activo. Todos los
comandos siguientes asumen ese contexto; `port_forward.sh` lo usa siempre (`--context kind-taller6`).

Argo necesita que los pods salgan a internet: clonar GitHub y bajar sus imágenes
(`quay.io/argoproj/argocd`, `ghcr.io/dexidp/dex`, `public.ecr.aws/docker/library/redis`):

```bash
kubectl run nettest --rm -it --restart=Never --image=curlimages/curl -- sh -c '
  for u in https://github.com https://quay.io https://ghcr.io https://public.ecr.aws; do
    printf "%s " "$u"; curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 "$u";
  done'
```

Cualquier código HTTP (200, 301, 302, 404) indica que hay salida; `000` indica bloqueo.

Si pods del clúster fallan con `too many open files`, subir los límites de inotify del host:

```bash
sudo sysctl fs.inotify.max_user_watches=524288 fs.inotify.max_user_instances=512
```

## Paso 3. Instalar Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f taller_6_argo/argocd/install.yaml
```

`--server-side` es necesario: el CRD de `ApplicationSet` es demasiado grande para un `apply` normal
(`metadata.annotations: Too long`).

```bash
kubectl -n argocd get pods -o wide -w
kubectl -n argocd rollout status deployment/argocd-server --timeout=10m
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=10m
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=10m
kubectl -n argocd get svc
kubectl api-resources | grep argoproj
```

Componentes: `argocd-server` (UI/API), `argocd-repo-server` (clona Git y renderiza Kustomize),
`argocd-application-controller` (compara y sincroniza), `argocd-redis`, `argocd-dex-server`,
`argocd-applicationset-controller`, `argocd-notifications-controller`.

## Paso 4. Port-forwards

Mismo patrón que `proyecto_2/scripts/port_forward.sh` (se relanzan si el pod se reinicia):

```bash
./taller_6_argo/scripts/port_forward.sh start
./taller_6_argo/scripts/port_forward.sh status
```

Abrir `https://10.43.97.106:8006` (certificado autofirmado, aceptar la advertencia). El forward de la
API (8005) queda en `FALLA` hasta el paso 7. Si `status` sigue en `FALLA` después de crear el Service,
relanzarlo con `start`.

Los puertos 8005 y 8006 están en el rango `8001-8010` que `proyecto_2/cluster/README.md` abre en
`firewalld`. Si no responden desde afuera:

```bash
sudo firewall-cmd --list-ports
sudo firewall-cmd --permanent --add-port=8005-8006/tcp && sudo firewall-cmd --reload
```

## Paso 5. Login y contraseña

```bash
argocd admin initial-password -n argocd
argocd login localhost:8006 --username admin --insecure
argocd account update-password
kubectl -n argocd delete secret argocd-initial-admin-secret
argocd cluster list
```

`argocd cluster list` debe mostrar `https://kubernetes.default.svc` (`in-cluster`): es el mismo clúster
donde corre Argo, así que no hace falta `argocd cluster add`.

## Paso 6. Prueba rápida con `guestbook` (opcional)

```bash
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default
argocd app get guestbook
argocd app sync guestbook
kubectl -n default get pods,svc -o wide
argocd app delete guestbook --yes
```

## Paso 7. Desplegar la API con Argo CD

Validar los manifiestos:

```bash
kubectl kustomize taller_6_argo/k8s
kubectl apply -k taller_6_argo/k8s --dry-run=server
```

Crear la Application (ya incluye `namespace: argocd`):

```bash
kubectl apply -f taller_6_argo/argocd/application.yaml
argocd app list
argocd app get taller6-housing
argocd app wait taller6-housing --health --timeout 300
```

Verificar:

```bash
kubectl -n taller6 get pods,svc -o wide
kubectl -n taller6 describe deployment taller6-housing
kubectl -n taller6 logs deploy/taller6-housing
./taller_6_argo/scripts/port_forward.sh status
curl http://10.43.97.106:8005/health
curl -X POST http://10.43.97.106:8005/predict -H 'Content-Type: application/json' \
  -d '{"barrio": "  Chapinero ", "area_m2": 80, "habitaciones": 3, "estrato": 4}'
```

`/predict` debe devolver `precio_estimado_cop = 480000000`, el mismo resultado de `taller_6`.

## Paso 8. Conectar el CI con Argo (actualizar el tag)

El workflow `.github/workflows/taller6-ci-cd.yml` tiene un tercer job, `update-manifest`, que corre
después de `publish-dockerhub` (solo en `push` a `master`):

1. Hace checkout de `master` con una **deploy key** que tiene permiso de escritura.
2. Cambia `newTag` en `taller_6_argo/k8s/kustomization.yaml` al SHA recién publicado.
3. Hace commit (`taller6: imagen <sha> [skip ci]`) y push directo a `master`. Si `master` avanzó
   mientras tanto, hace `pull --rebase` y reintenta hasta 3 veces.

```text
unit-tests -> publish-dockerhub -> update-manifest -> commit en master -> Argo CD sync
```

El ruleset de `master` exige PR y status check, así que el push del job necesita una excepción. Se usa
una deploy key porque es la única excepción que GitHub permite siempre en un repo personal, y solo la
tiene este job. El commit del bot no dispara otro ciclo: solo cambia `taller_6_argo/`, que no está en el
`paths` del workflow, y además lleva `[skip ci]`. El `concurrency` evita que dos merges seguidos
escriban el tag al mismo tiempo.

### 8.1 Crear la deploy key

En cualquier equipo:

```bash
ssh-keygen -t ed25519 -C "taller6-argo-deploy" -f taller6_deploy_key -N ""
```

| Dónde | Qué |
|---|---|
| `Settings > Deploy keys > Add deploy key` | Título `taller6-argo-deploy`, contenido de `taller6_deploy_key.pub`, marcar **Allow write access** |
| `Settings > Secrets and variables > Actions > Secrets` | Secret `DEPLOY_KEY` con el contenido de `taller6_deploy_key` (la llave privada) |

Después se borran los dos archivos locales: `rm taller6_deploy_key taller6_deploy_key.pub`.

### 8.2 Excepción en el ruleset de `master`

`Settings > Rules > Rulesets >` (ruleset de `master`) `> Bypass list > Add bypass > Deploy keys`,
modo **Always allow**, y guardar. Las PRs normales siguen exigiendo el status check `unit-tests`.

### 8.3 Probar

Las llaves y la excepción del ruleset deben estar configuradas **antes** de mergear el workflow: el
propio merge cambia `.github/workflows/taller6-ci-cd.yml`, dispara los tres jobs y es la primera prueba.

```bash
git log --oneline -3 origin/master              # commit "taller6: imagen ... [skip ci]"
grep newTag taller_6_argo/k8s/kustomization.yaml
argocd app get taller6-housing --refresh
kubectl -n taller6 get pods -o wide
kubectl -n taller6 get deploy taller6-housing -o jsonpath='{.spec.template.spec.containers[0].image}'
```

Si el job falla con `Permission denied (publickey)` falta la deploy key o el secret; si falla con
`GH013: Repository rule violations`, falta la excepción del ruleset.

## Paso 9. Evidencias GitOps

| Prueba | Comando / acción | Resultado esperado |
|---|---|---|
| Despliegue por commit | merge de un cambio en `taller_6/unit_testing` | CI pasa, `update-manifest` escribe el tag, Argo `Synced` y pods nuevos |
| Self-heal | `kubectl -n taller6 scale deployment taller6-housing --replicas=5` | Argo vuelve a 2 réplicas |
| Drift visible | `argocd app set taller6-housing --self-heal=false` y luego el `scale` anterior | `OutOfSync` y diff en la UI (`argocd app diff taller6-housing`) |
| Prune | quitar `service.yaml` del `kustomization.yaml` y hacer commit | Argo borra el Service |
| Rollback | `git revert` del commit del tag | vuelve la imagen anterior |
| CI fallido | PR con una prueba rota | no se publica imagen, Argo no cambia nada |

```bash
argocd app history taller6-housing
argocd app diff taller6-housing
kubectl -n taller6 rollout history deployment/taller6-housing
kubectl -n taller6 get events --sort-by=.lastTimestamp
```

## Limpieza

```bash
./taller_6_argo/scripts/port_forward.sh stop
argocd app delete taller6-housing --yes
kubectl delete namespace taller6
kubectl delete -n argocd -f taller_6_argo/argocd/install.yaml
kubectl delete namespace argocd
kind delete cluster --name taller6               # borra todo el clúster de la 106
```

---

## Comandos de Kubernetes de referencia (proyecto_2 y talleres)

kind:

```bash
kind create cluster --config taller_6_argo/kind-config.yaml
kind get clusters
kind load docker-image <imagen>:<tag> --name taller6    # usar una imagen local sin Docker Hub
kind delete cluster --name taller6
docker exec -it taller6-control-plane crictl images      # imágenes dentro del nodo
```

Contexto y nodos:

```bash
kubectl config get-contexts
kubectl config use-context kind-taller6
kubectl config current-context
kubectl config set-context --current --namespace=<ns>
kubectl get nodes -o wide
kubectl get nodes -L mlops/tier
kubectl label node <nodo> mlops/tier=serving
kubectl top nodes
kubectl top pods -n <ns>
```

Aplicar y borrar:

```bash
kubectl apply -f <archivo.yaml>
kubectl apply -k <carpeta>                    # kustomize
kubectl kustomize <carpeta>                   # ver el YAML renderizado
kubectl apply -k <carpeta> --dry-run=server
kubectl delete -k <carpeta>
kubectl create namespace <ns>
kubectl delete namespace <ns>
```

Estado:

```bash
kubectl -n <ns> get pods -o wide
kubectl -n <ns> get pods -w
kubectl -n <ns> get all
kubectl -n <ns> get svc,pvc,configmap,secret
kubectl -n <ns> describe pod <pod>
kubectl -n <ns> get events --sort-by=.lastTimestamp
kubectl -n <ns> rollout status deployment/<deploy> --timeout=10m
kubectl -n <ns> rollout status statefulset/<sts> --timeout=10m
kubectl -n <ns> wait --for=condition=complete job/<job> --timeout=5m
```

Logs, shell y acceso:

```bash
kubectl -n <ns> logs -f deploy/<deploy>
kubectl -n <ns> logs <pod> --previous
kubectl -n <ns> exec -it <pod> -- sh
kubectl -n <ns> port-forward --address 0.0.0.0 svc/<svc> <local>:<remoto>
kubectl run nettest --rm -it --restart=Never --image=curlimages/curl -- curl -sI <url>
```

Escalar, actualizar y revertir:

```bash
kubectl -n <ns> scale deployment <deploy> --replicas=3
kubectl -n <ns> set image deployment/<deploy> <contenedor>=<imagen>:<tag>
kubectl -n <ns> rollout restart deployment/<deploy>
kubectl -n <ns> rollout history deployment/<deploy>
kubectl -n <ns> rollout undo deployment/<deploy>
```

Parches, StorageClass y firewall:

```bash
kubectl patch svc <svc> -n <ns> -p '{"spec": {"type": "NodePort"}}'
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
kubectl get storageclass
sudo firewall-cmd --permanent --add-port=<puerto>/tcp && sudo firewall-cmd --reload
```

Helm:

```bash
helm repo add <nombre> <url>
helm repo update
helm upgrade --install <release> <chart> --version <v> -n <ns> -f values.yaml --wait --timeout 20m
helm list -A
helm uninstall <release> -n <ns>
```

Docker en la VM:

```bash
docker ps
docker compose -f <archivo> down
docker rm -f <contenedor>
ss -ltnp | grep <puerto>
docker buildx imagetools inspect <usuario>/<imagen>:<tag>
```

Argo CD:

```bash
argocd login localhost:8006 --username admin --insecure
argocd app list
argocd app get <app>
argocd app get <app> --refresh
argocd app sync <app>
argocd app wait <app> --health --timeout 300
argocd app diff <app>
argocd app history <app>
argocd app rollback <app> <ID>                 # solo con auto-sync apagado
argocd app set <app> --self-heal=false
argocd app set <app> --sync-policy none        # apagar auto-sync
argocd app delete <app> --yes
argocd repo list
argocd cluster list
```
