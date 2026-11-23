# Argo CD

Argo CD sincroniza el clúster con este repositorio (GitOps). Se instala una sola vez con `cluster/bootstrap.sh` (`install/install.yaml`, v3.6.1) y desde ahí todo el despliegue sale de Git.

## App-of-apps

| Archivo | App | Qué sincroniza |
|---|---|---|
| `root.yaml` | `housing-root` | La carpeta `apps/`: crea o actualiza una app de Argo por cada archivo |
| `apps/data-platform.yaml` | `data-platform` | `platform/`: namespace, PostgreSQL de datos, MinIO, MLflow y API de datos |
| `apps/airflow.yaml` | `airflow` | Chart oficial de Airflow 1.22.0 con `airflow/values.yaml` (multi-source) y `airflow/k8s/`: PostgreSQL de metadatos y ConfigMap del pipeline |
| `apps/serving.yaml` | `serving` | `serving/`: API de inferencia (2 réplicas en el nodo de serving); luego Streamlit |
| `apps/observability.yaml` | `observability` | `observability/`: Prometheus y Grafana con el dashboard "Housing API" en el nodo de serving |

Streamlit se agrega a `serving/` y Locust a `observability/`. Una app nueva es un archivo más en `apps/` (y en `apps/kustomization.yaml`); la app raíz la crea sola en la siguiente sincronización.

Todas usan `automated` con `prune` y `selfHeal`: un cambio en `master` se aplica solo (cada 3 minutos o con **Refresh**) y un cambio manual en el clúster se revierte al estado de Git. Las apps no llevan el finalizer de borrado en cascada: borrar una app en Argo no borra sus recursos. El namespace y el PVC de la API de datos además tienen `Prune=false,Delete=false`.

## Aplicar la app raíz (una sola vez)

Requisitos: el clúster con `cluster/bootstrap.sh` y los Secrets con `scripts/create_secrets.sh`. En la .106:

```bash
kubectl config current-context        # housing
kubectl apply -n argocd -f argocd/root.yaml
argocd app list
argocd app get data-platform
kubectl -n housing-mlops get pods -o wide
```

Es el único `kubectl apply` del proyecto fuera del bootstrap: Argo no puede crear su propia app raíz.

## Ciclo GitOps de una imagen

1. Un push a `master` que cambia `mlflow/` dispara `Build MLflow` en GitHub Actions.
2. El workflow publica `crissebasbol/housing-mlflow:sha-<7>` en DockerHub y hace un commit `Imagen mlflow sha-<7> [skip ci]` que cambia el tag en `mlflow/k8s/deployment.yaml`.
3. Argo detecta el commit, sincroniza `data-platform` y el Deployment de MLflow se actualiza a la imagen nueva.

En la UI de Argo, **History and Rollback** de la app muestra cada sincronización con su commit.
