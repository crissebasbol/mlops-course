# API de inferencia (Covertype + MLflow)

API REST con FastAPI que predice el tipo de cobertura forestal con el modelo
`covertype_rf@champion` del Model Registry de MLflow.

## Endpoints

| Método | Ruta       | Descripción                                          |
|--------|------------|------------------------------------------------------|
| GET    | `/health`  | `200` cuando el modelo ya está cargado. Lo usa el healthcheck. |
| GET    | `/model`   | Versión y run que tiene esta réplica en memoria.     |
| GET    | `/models`  | Versiones registradas en MLflow, con alias, parámetros y métricas. |
| GET    | `/models/{version}` | Detalle de una versión; `404` con las disponibles si no existe. |
| POST   | `/predict` | Predice el `cover_type` con el `champion` en memoria. |

Documentación: http://10.43.97.105:8000/docs

## Imagen en Docker Hub

`crissebasbol/taller5-api:1.0.0` (también `latest`). Se publica desde la raíz de
`taller_5` con:

```bash
docker login
docker buildx build --platform linux/amd64,linux/arm64 \
  -t crissebasbol/taller5-api:1.0.0 \
  -t crissebasbol/taller5-api:latest \
  --push api
```

Variables del `docker compose`:

| Variable     | Por defecto | Para qué sirve                        |
|--------------|-------------|---------------------------------------|
| `API_TAG`    | `1.0.0`     | Tag de la imagen de Docker Hub.       |
| `API_CPUS`   | `1.0`       | Límite de CPU **por réplica**.        |
| `API_MEMORY` | `1g`        | Límite de memoria **por réplica**.    |