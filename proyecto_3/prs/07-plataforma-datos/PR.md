# PR 7: plataforma de datos (Cristian Organista)

**Depende del PR 6** (base de datos): abrirlo cuando el PR 6 esté fusionado, porque reemplaza `scripts/create_secrets.sh` con la versión que agrega los Secrets de MinIO y MLflow.

Probado en local con Docker: MinIO con su script de setup (corrido dos veces, es idempotente), el Postgres de MLflow, la imagen de MLflow construida desde este Dockerfile y un modelo de `housing_ml` registrado, con alias `champion` y cargado por alias sin credenciales de MinIO. También se probaron los permisos de cada usuario de MinIO, se validaron los manifiestos con `kubeconform` y los workflows con `actionlint`.

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/plataforma-datos

# copiar el contenido de esta carpeta (incluida .github/) sobre la raíz del repo
chmod +x minio/setup.sh mlflow/start.sh scripts/create_secrets.sh

uv run ruff check . && uv run pytest -q
kubectl kustomize platform | head -20      # opcional, en la .106 o con kubectl local

git add namespace data-api
git commit -m "Namespace, LimitRange y API de datos propia"
git add minio
git commit -m "MinIO con buckets, usuarios y políticas por servicio"
git add mlflow
git commit -m "MLflow con Postgres propio y proxy de artefactos"
git add platform scripts/create_secrets.sh
git commit -m "Agregación de la plataforma y Secrets de MinIO y MLflow"
git add .github/workflows
git commit -m "Validación de manifiestos y build de la imagen de MLflow"
git push -u origin feature/plataforma-datos
```

**Título del PR:** `Plataforma de datos: MinIO, MLflow y API de datos`

**Qué cambia**

- `namespace/`: namespace `housing-mlops` y un `LimitRange` con valores por defecto para contenedores sin recursos (los init containers del chart de Airflow).
- `data-api/`: la imagen de la API de datos del curso desplegada en el clúster (1 réplica, estrategia `Recreate`, PVC de 100 Mi para su contador de lotes).
- `minio/`: StatefulSet con PVC de 20 Gi y un Job (hook `PostSync` de Argo CD) que crea los buckets `mlflow`, `landing` y `datasets`, tres políticas y tres usuarios:
  - `mlflow`: lee y escribe solo el bucket `mlflow`;
  - `airflow`: lee y escribe `landing` y `datasets`;
  - `locust`: solo lee `datasets/replay/`.
- `mlflow/`: imagen propia (MLflow 3.16.1, sin root), Postgres propio para metadatos y servidor con `--serve-artifacts`: los clientes guardan y cargan modelos a través de MLflow, sin credenciales de MinIO. La URI de Postgres la arma `start.sh` con variables de entorno, así la contraseña no aparece en el manifiesto.
- `platform/`: une namespace, base de datos, MinIO, MLflow y API de datos para que Argo CD los sincronice como una sola aplicación.
- `scripts/create_secrets.sh`: agrega los Secrets `postgres-mlflow`, `minio-root`, `minio-mlflow`, `minio-airflow` y `minio-locust`.
- `.github/workflows/`:
  - `ci.yml`: nuevo job `manifests` que renderiza cada kustomization y lo valida con `kubeconform`;
  - `_build-push.yml`: workflow reutilizable que construye la imagen (`linux/amd64`), la publica con tag `sha-<7>` y actualiza el tag en el manifiesto con la deploy key, para que Argo CD sincronice;
  - `build-mlflow.yml`: lo usa para la imagen de MLflow.

**Por qué**

- Enunciado 6.3 a 6.5: MLflow con base de metadatos externa (no SQLite) y artefactos en un bucket, y documentar bucket, credenciales y políticas.
- C9: la API de datos también corre en el clúster.
- Mínimo privilegio: cada servicio con su usuario; en proyecto_2 MLflow usaba el usuario root de MinIO y la contraseña de Postgres quedaba en la URI del manifiesto.
- C8: imágenes versionadas por SHA y actualización del manifiesto por CI (GitOps).

**Cómo se probó**

- [x] `uv run ruff check .` y `uv run pytest`
- [x] Integración local con Docker (MinIO, setup, Postgres, MLflow, registro y carga de un modelo por alias)
- [x] Permisos de MinIO: lo permitido funciona y lo prohibido falla
- [x] `kubeconform` (18 recursos válidos) y `actionlint`

## Después de fusionar

- El workflow `Build MLflow` corre solo: publica `crissebasbol/housing-mlflow:sha-<7>` y hace un commit `Imagen mlflow sha-<7> [skip ci]` que reemplaza el tag `bootstrap` del `deployment.yaml`. Revisar que ese commit aparezca en `master`.
- Agregar el job `manifests` como *status check* obligatorio en el ruleset de `master`, junto a `ci`.

## Para explicarlo

- **¿Por qué MLflow sirve los artefactos?** Con `--serve-artifacts`, Airflow y la API hablan solo con MLflow (`mlflow-artifacts:/`); solo MLflow tiene credenciales de MinIO. Los clientes deben tener `MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false`: en la prueba local, sin esa variable el cliente intentaba descargar directo de MinIO con URLs prefirmadas.
- **¿Por qué el Job de MinIO es un hook `PostSync`?** Corre después de cada sincronización de Argo; como el script es idempotente (crea solo lo que falta), repetirlo no rompe nada y repara un usuario o una política borrados.
- **¿Por qué el tag de la imagen está escrito en el `deployment.yaml`?** Así el manifiesto dice exactamente qué versión corre, y el CI lo actualiza con `yq` en cada build.
- **¿Por qué `Recreate` en la API de datos?** Su PVC es `ReadWriteOnce`: con `RollingUpdate`, el pod nuevo no podría montar el volumen mientras el viejo siga vivo.
