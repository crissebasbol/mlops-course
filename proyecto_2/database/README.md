# database

`postgres-data`: StatefulSet de Postgres 16 con la base `diabetes` (PVC de 5 Gi, nodo `data`).

Los scripts de `init/` se montan como ConfigMap en `/docker-entrypoint-initdb.d` y solo
corren cuando el volumen está vacío:

- `01_roles.sh`: crea los usuarios `airflow_etl` y `api_writer` con las contraseñas del Secret `postgres-data`.
- `02_tables.sql`: schemas `raw`, `clean`, `inference` y sus tablas.

| Tabla | Contenido |
|---|---|
| `raw.batches` | Control de lotes: rango de filas, conteos y `status` |
| `raw.diabetes` | CSV sin transformar + `row_hash`, `batch_id`, `load_timestamp`, `source_file`, `source_row`, `status`, `status_reason` |
| `clean.diabetes` | Features limpias, `split`, `readmitted` y `target` |
| `inference.predictions` | Cada `/predict`: entrada (JSONB), predicción, probabilidades, modelo, versión, alias, latencia, `request_id` |

Para recrear las tablas desde cero hay que borrar el PVC:

```bash
kubectl -n proyecto2 delete statefulset postgres-data
kubectl -n proyecto2 delete pvc data-postgres-data-0
kubectl apply -k .
```
