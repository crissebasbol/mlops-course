# API de inferencia

FastAPI que sirve el modelo `champion` del registro de MLflow (`housing-price-model`). No tiene versiones ni rutas fijas: resuelve los alias en cada revisión.

| Endpoint | Uso |
|---|---|
| `POST /predict` | Precio estimado. Valida con los mismos rangos de `housing_ml.cleaning.RANGES` que el pipeline. Headers opcionales `X-Traffic-Source` (`api`, `streamlit`, `locust`, `replay`) y `X-Replay-Row` (hash de la fila del holdout) |
| `POST /explain` | Contribuciones SHAP de la predicción en escala log del precio y su efecto en % (`effect_pct = (e^shap - 1) × 100`) |
| `POST /feedback` | Precio real de una predicción (`request_id`, `actual_price`) |
| `GET /model-info` | Champion y sombra cargados: versión, run, métricas y hora de carga |
| `POST /admin/reload` | Revisa los alias ya (Bearer `API_ADMIN_TOKEN`) |
| `POST /admin/rollback` | `champion` vuelve a `previous_champion`; la versión retirada queda como `previous_champion` y con el tag `rolled_back` |
| `GET /health`, `GET /metrics`, `GET /docs` | Salud (200 aunque no haya modelo), Prometheus y Swagger |

## Cómo funciona

- **Recarga sin reinicio:** un hilo revisa los alias cada `RELOAD_INTERVAL_SECONDS` (30 s). Solo descarga cuando cambia la versión, la carga fuera del lock y cambia champion y sombra en un solo paso. Si la descarga falla, sigue con el modelo anterior y suma `model_reload_failures_total`. Cada cambio queda en `audit.model_actions` (`reload`, con el pod como actor).
- **Sombra:** si `challenger` es distinto de `champion`, la API también lo evalúa después de responder y guarda las dos predicciones y latencias en el mismo evento. Al promover, el challenger ya cargado pasa a champion sin volver a descargarlo.
- **Registro de inferencias:** cola en memoria y escritura por lotes en un hilo (`raw.inference_events`, rol `api_writer`). Postgres no suma latencia a `/predict`; si falla, la predicción sigue y sube `inference_log_errors_total`. También se registran las respuestas 422 y 503.
- **Un hilo por predicción:** `OMP_NUM_THREADS=1`, igual que la compuerta G6 al medir la latencia.
- **Sin champion:** `/predict` responde 503 con la explicación y `/health` sigue en 200 con `model_loaded=false`.

## Ejemplo

```bash
curl -X POST http://10.43.97.106:8005/predict -H 'Content-Type: application/json' \
  -d '{"status":"for_sale","bed":3,"bath":2,"acre_lot":0.25,"house_size":1800,
       "prev_sold_date":"2015-06-15","city":"Springfield","state":"Massachusetts",
       "zip_code":"01109","brokered_by":"22611"}'

curl -X POST http://10.43.97.106:8005/admin/rollback -H "Authorization: Bearer $API_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"reason":"Sube el error en producción","actor":"equipo"}'
```

## Variables

| Variable | Origen | Valor |
|---|---|---|
| `MLFLOW_TRACKING_URI`, `MODEL_NAME`, `RELOAD_INTERVAL_SECONDS`, `SHADOW_ENABLED`, `DATA_DB_*` | ConfigMap `api` | `http://mlflow:5000`, `housing-price-model`, `30`, `true`, `postgres-data/housing/api_writer` |
| `DATA_DB_PASSWORD` | Secret `postgres-data` | clave `API_WRITER_PASSWORD` |
| `API_ADMIN_TOKEN` | Secret `api-admin` | clave `token` |
