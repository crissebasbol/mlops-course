# API de inferencia (Covertype + MLflow)

API REST con FastAPI que predice el tipo de cobertura forestal usando el modelo
`covertype_rf` del **Model Registry de MLflow**. La API no lee archivos ni
buckets directamente: pide el modelo a MLflow con una URI `models:/...` y MLflow
resuelve dónde está el artefacto (MinIO, bucket `mlflows3`).

## Cómo toma el modelo

- Sin `version`: usa la versión a la que apunta el alias **`champion`**
  (`MODEL_ALIAS`). El alias se resuelve en cada petición, así que si se mueve en
  MLflow (desde el notebook o la UI) la API empieza a usar el nuevo modelo sin
  reiniciarse.
- Con `version`: usa `models:/covertype_rf/<version>`. Si no existe responde
  **404** con las versiones disponibles.

Cada versión descargada se guarda en memoria (las últimas `MODEL_CACHE_SIZE`,
4 por defecto).

## Endpoints

| Método | Ruta               | Descripción                                                          |
|--------|--------------------|----------------------------------------------------------------------|
| GET    | `/health`          | Estado del servicio y conexión con MLflow.                           |
| GET    | `/models`          | Versiones registradas, sus alias, parámetros y métricas del run.     |
| GET    | `/models/{version}`| Detalle de una versión.                                              |
| POST   | `/predict`         | Predice el `cover_type` con el alias `champion` o la versión indicada. |

Documentación interactiva: http://10.43.97.92:8018/docs

## Variables de entorno

| Variable                 | Por defecto           | Para qué sirve                                   |
|--------------------------|-----------------------|--------------------------------------------------|
| `MLFLOW_TRACKING_URI`    | `http://mlflow:5000`  | Servidor de MLflow.                              |
| `MLFLOW_S3_ENDPOINT_URL` | `http://minio:9000`   | MinIO, para descargar los artefactos del modelo. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | `admin` / `admin123` | Credenciales de MinIO.           |
| `MODEL_NAME`             | `covertype_rf`        | Modelo registrado que se sirve.                  |
| `MODEL_ALIAS`            | `champion`            | Alias que se usa cuando no se pide versión.      |
| `MODEL_CACHE_SIZE`       | `4`                   | Versiones que se mantienen en memoria.           |