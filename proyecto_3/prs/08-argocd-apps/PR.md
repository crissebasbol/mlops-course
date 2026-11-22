# PR 8: apps de Argo CD (Cristian Organista)

**Depende de los PRs 7a y 7b.** Orden: 7a (plataforma) → 7b (publica la imagen de MLflow y cambia su tag) → 8. Si Argo sincroniza antes del 7b, el pod de MLflow queda en `ImagePullBackOff` porque el tag `bootstrap` no existe en DockerHub (se arregla solo cuando llegue el 7b, pero es mejor no confundirse).

Validado con `kubeconform` contra el esquema del CRD `Application` de Argo CD.

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/argocd-apps

# copiar el contenido de este directorio sobre la raíz del repo:
# argocd/ (agrega root.yaml, README.md y apps/; no toca argocd/install/),
# namespace/namespace.yaml y data-api/k8s/pvc.yaml (reemplazan los actuales)

git add namespace/namespace.yaml data-api/k8s/pvc.yaml
git commit -m "Argo CD no borra el namespace ni el PVC de la API de datos"
git add argocd/root.yaml argocd/apps argocd/README.md
git commit -m "Apps de Argo CD: raíz y plataforma de datos"
git push -u origin feature/argocd-apps
```

**Título del PR:** `Apps de Argo CD para la plataforma de datos`

**Qué cambia**

- `argocd/root.yaml`: app raíz `housing-root` (patrón *app-of-apps*) que sincroniza `argocd/apps/`.
- `argocd/apps/data-platform.yaml`: app `data-platform` que sincroniza `platform/` (namespace, PostgreSQL de datos, MinIO, MLflow y API de datos) en `housing-mlops`, con `automated`, `prune`, `selfHeal` y reintentos.
- `argocd/apps/kustomization.yaml`: lista de apps (la CI la valida con `kubeconform`).
- `argocd/README.md`: cómo funciona, cómo aplicar la app raíz y el ciclo GitOps de una imagen.
- `namespace/namespace.yaml` y `data-api/k8s/pvc.yaml`: anotación `argocd.argoproj.io/sync-options: Prune=false,Delete=false`. El namespace guarda los Secrets creados a mano y los volúmenes con datos: Argo nunca los borra, aunque se borre la app o el archivo salga de Git.

**Por qué**

Enunciado 6.15 y C8: Argo CD es el mecanismo de despliegue. Con app-of-apps, cada componente nuevo (Airflow, API, Streamlit, observabilidad, Locust) es un archivo más en `argocd/apps/`, sin tocar el clúster a mano.

**Cómo se probó**

- [x] `kubeconform` con el esquema del CRD de Argo
- [ ] Sincronización en el clúster (completar con lo que pasó)

## Después de fusionar (en la .106)

```bash
cd ~/housing-price-mlops && git switch master && git pull
kubectl -n housing-mlops get secrets                 # deben estar los 6 (create_secrets.sh después del 7a)
kubectl config current-context                       # housing
kubectl apply -n argocd -f argocd/root.yaml
argocd app list
argocd app get data-platform
kubectl -n housing-mlops get pods -o wide -w         # Ctrl+C cuando todo esté Running
kubectl -n housing-mlops get jobs,pvc
kubectl -n housing-mlops logs job/minio-setup
./scripts/port_forward.sh start && ./scripts/port_forward.sh status
```

Verificar:

| Qué | Cómo | Esperado |
|---|---|---|
| Apps | UI de Argo (`https://10.43.97.106:8006`) | `housing-root` y `data-platform` en *Synced* y *Healthy* |
| Pods | `kubectl -n housing-mlops get pods -o wide` | `postgres-data-0`, `postgres-mlflow-0`, `minio-0` y `data-api` en `nodo-data`, todos `Running` |
| MinIO | `kubectl logs job/minio-setup` | Buckets `mlflow`, `landing`, `datasets` y usuarios `mlflow`, `airflow`, `locust` |
| MLflow | `http://10.43.97.106:8003` | UI de MLflow sin experimentos |
| API de datos | `curl http://10.43.97.106:8011/health` | `{"status":"OK"}` (no llamar `/data`: consume lotes) |

**Capturas para el README** (sin contraseñas ni tokens): las dos apps *Synced/Healthy* en Argo, el árbol de recursos de `data-platform`, `kubectl get pods -o wide`, el log del Job de MinIO y la UI de MLflow.

## Para explicarlo

- **¿Qué es app-of-apps?** Una app de Argo cuyo contenido son otras apps. Se aplica a mano solo la raíz; las demás salen de Git.
- **¿Por qué no hay finalizer de borrado en cascada?** Para que borrar una app en Argo no borre bases de datos ni volúmenes por accidente.
- **¿Qué hacen `prune` y `selfHeal`?** `prune` borra del clúster lo que se quita de Git; `selfHeal` revierte cambios hechos a mano en el clúster.
