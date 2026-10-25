# api

API de inferencia con FastAPI (`crissebasbol/proyecto2-api`), 2 réplicas en el nodo `serving`.

| Endpoint | Descripción |
|---|---|
| `GET /health` | Estado de la réplica, si hay modelo cargado y si la base responde |
| `POST /predict` | Predice y registra la inferencia en `inference.predictions` |
| `GET /model-info` | Nombre, alias, versión, run, tipo y métricas del modelo en memoria |
| `POST /reload` | Fuerza la revisión del alias en MLflow |
| `GET /metrics` | Métricas Prometheus |

Desarrollo local:

```bash
cd api
uv sync
MLFLOW_TRACKING_URI=http://localhost:8003 DATA_DB_HOST=localhost uv run uvicorn api:app --reload
```
