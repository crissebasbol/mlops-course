# PR 7a: plataforma de datos (Fabián Ramírez)

Depende del PR 6 (ya fusionado). Puede abrirse ya. Después de fusionarlo, Cristhian Bolaños abre el PR 7b (validación de manifiestos en la CI y build de la imagen de MLflow), y en la .106 se corre `bash scripts/create_secrets.sh` (después de `git switch master && git pull`) para crear los Secrets de MinIO y MLflow. Después de fusionarlo, Cristhian Bolaños abre el PR 7b (validación de manifiestos en la CI y build de la imagen de MLflow).

Probado en local con Docker: MinIO con su script de setup (corrido dos veces, es idempotente), el Postgres de MLflow, la imagen de MLflow construida desde este Dockerfile y un modelo de `housing_ml` registrado, con alias `champion` y cargado por alias sin credenciales de MinIO. También se probaron los permisos de cada usuario de MinIO y se validaron los manifiestos con `kubeconform` (18 recursos válidos).

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/plataforma-datos

# copiar el contenido de esta carpeta sobre la raíz del repo
# (reemplaza scripts/create_secrets.sh con la versión que agrega MinIO y MLflow)
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
git update-index --chmod=+x scripts/create_secrets.sh minio/setup.sh mlflow/start.sh
git commit -m "Agregación de la plataforma y Secrets de MinIO y MLflow"
git push -u origin feature/plataforma-datos
```

`git update-index --chmod=+x` deja los scripts con permiso de ejecución en Git (en el PR 6, `create_secrets.sh` quedó sin él).

**Título del PR:** `Plataforma de datos: MinIO, MLflow y API de datos`

**Qué cambia**

- `namespace/`: namespace `housing-mlops` y un `LimitRange` con valores por defecto para contenedores sin recursos (los init containers del chart de Airflow).
- `data-api/`: la imagen de la API de datos del curso desplegada en el clúster (1 réplica, estrategia `Recreate`, PVC de 100 Mi para su contador de lotes).
- `minio/`: StatefulSet con PVC de 20 Gi y un Job (hook `PostSync` de Argo CD) que crea los buckets `mlflow`, `landing` y `datasets`, tres políticas y tres usuarios:
  - `mlflow`: lee y escribe solo el bucket `mlflow`;
  - `airflow`: lee y escribe `landing` y `datasets`;
  - `locust`: solo lee `datasets/replay/`.
- `mlflow/`: imagen propia (MLflow 3.16.1, sin root), Postgres propio para metadatos y servidor con `--serve-artifacts`: los clientes guardan y cargan modelos a través de MLflow, sin credenciales de MinIO. La URI de Postgres la arma `start.sh` con variables de entorno, así la contraseña no aparece en el manifiesto. El `deployment.yaml` trae el tag `bootstrap`; el PR 7b publica la imagen real y el CI reemplaza ese tag.
- `platform/`: une namespace, base de datos, MinIO, MLflow y API de datos para que Argo CD los sincronice como una sola aplicación.
- `scripts/create_secrets.sh`: agrega los Secrets `postgres-mlflow`, `minio-root`, `minio-mlflow`, `minio-airflow` y `minio-locust`.

**Por qué**

- Enunciado 6.3 a 6.5: MLflow con base de metadatos externa (no SQLite) y artefactos en un bucket, y documentar bucket, credenciales y políticas.
- C9: la API de datos también corre en el clúster.
- Mínimo privilegio: cada servicio con su usuario; en proyecto_2 MLflow usaba el usuario root de MinIO y la contraseña de Postgres quedaba en la URI del manifiesto.

**Cómo se probó**

- [x] `uv run ruff check .` y `uv run pytest`
- [x] Integración local con Docker (MinIO, setup, Postgres, MLflow, registro y carga de un modelo por alias)
- [x] Permisos de MinIO: lo permitido funciona y lo prohibido falla
- [x] `kubeconform`: 18 recursos válidos

## Para explicarlo

- **¿Por qué MLflow sirve los artefactos?** Con `--serve-artifacts`, Airflow y la API hablan solo con MLflow (`mlflow-artifacts:/`); solo MLflow tiene credenciales de MinIO. Los clientes deben tener `MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false`: en la prueba local, sin esa variable el cliente intentaba descargar directo de MinIO con URLs prefirmadas.
- **¿Por qué el Job de MinIO es un hook `PostSync`?** Corre después de cada sincronización de Argo; como el script es idempotente (crea solo lo que falta), repetirlo no rompe nada y repara un usuario o una política borrados.
- **¿Por qué el tag de la imagen está escrito en el `deployment.yaml`?** Así el manifiesto dice exactamente qué versión corre, y el CI lo actualiza en cada build (PR 7b).
- **¿Por qué `Recreate` en la API de datos?** Su PVC es `ReadWriteOnce`: con `RollingUpdate`, el pod nuevo no podría montar el volumen mientras el viejo siga vivo.
- **La imagen de MinIO no trae `grep`**: el script de setup usa solo comandos de shell (se encontró en la prueba local).
