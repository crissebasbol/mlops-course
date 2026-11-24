# Capturas que faltan para el README

Todo en la **.106** (`cd ~/housing-price-mlops && git pull`), salvo las que son de navegador. Cada captura sin contraseñas ni tokens a la vista. Nombre sugerido entre paréntesis.

## 1. Pods del clúster con sus recursos (`k8s_01_pods_recursos`)

```bash
kubectl get nodes -o wide
kubectl -n housing-mlops get pods -o custom-columns=POD:.metadata.name,NODO:.spec.nodeName,ESTADO:.status.phase,CPU_REQ:.spec.containers[0].resources.requests.cpu,CPU_LIM:.spec.containers[0].resources.limits.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory,MEM_LIM:.spec.containers[0].resources.limits.memory
```

Una captura con las dos salidas (o dos capturas).

## 2. RAW y CLEAN con su trazabilidad por lote (`datos_01_raw_clean`)

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "
WITH r AS (SELECT ingestion_id, count(*) AS raw, count(*) FILTER (WHERE quality_status = 'rejected') AS rechazadas FROM raw.properties GROUP BY 1),
     c AS (SELECT ingestion_id, count(*) AS clean FROM clean.properties GROUP BY 1)
SELECT b.ingestion_id AS ingreso, b.cycle AS ciclo, b.api_batch_number AS lote, b.outcome, b.record_count AS filas_api,
       left(b.data_sha256, 12) AS sha256, b.duplicate_of AS repite, r.raw, r.rechazadas, c.clean
FROM raw.batches b LEFT JOIN r USING (ingestion_id) LEFT JOIN c USING (ingestion_id)
WHERE b.ingestion_id <= 10 ORDER BY 1"
```

Y una fila de CLEAN unida a su fila RAW original (`datos_02_fila_trazable`):

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "
SELECT c.ingestion_id AS ingreso, left(c.row_hash, 12) AS row_hash, c.split, c.price AS precio_clean,
       r.payload->>'price' AS precio_raw, c.zip_code, r.payload->>'zip_code' AS zip_raw, r.quality_status
FROM clean.properties c JOIN raw.properties r ON r.row_hash = c.row_hash AND r.ingestion_id = c.ingestion_id
WHERE c.ingestion_id = 5 LIMIT 5"
```

## 3. Registro de inferencias (`api_09_registro_inferencias`)

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "
SELECT traffic_source, status, count(*) FROM raw.inference_events GROUP BY 1, 2 ORDER BY 3 DESC"
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "
SELECT to_char(ts, 'MM-DD HH24:MI:SS') AS ts, traffic_source AS origen, endpoint, status_code, status,
       champion_version AS champ, round(prediction) AS prediccion, shadow_version AS sombra,
       round(shadow_prediction) AS pred_sombra, round(champion_latency_ms) AS ms
FROM raw.inference_events ORDER BY ts DESC LIMIT 12"
```

## 4. Monitoreo del champion en un ciclo de repetidos (`pipeline_09_monitoreo`)

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "
SELECT cycle AS ciclo, api_batch_number AS lote, champion_version_before AS champion,
       round(champion_mape_on_batch::numeric * 100, 2) AS mape_pct, left(training_reason, 90) AS razon
FROM audit.batch_runs WHERE cycle = 2 ORDER BY ingestion_id"
```

## 5. MLflow: registro de modelos (`mlflow_04_registro_alias`)

Navegador, `http://10.43.97.106:8003` → **Models** → `housing-price-model`: la lista de versiones 1 a 5 con sus alias (`champion` en 4, `challenger` en 5, `previous_champion` en 3).

## 6. MLflow: artefactos del champion (`mlflow_05_shap`, `mlflow_06_graficos`)

Experimento `housing-price` → run `c1-b4-...` (versión 4) → **Artifacts**:
- `shap/shap_beeswarm.png` abierto;
- `plots/val_mape_por_banda.png` o `plots/val_predicho_vs_real.png` abierto.

## 7. Validaciones y drift de un lote (`streamlit_09_detalle_drift`, `streamlit_10_detalle_compuertas`)

Streamlit `http://10.43.97.106:8007` → **Historial de lotes** → "Detalle de un ingreso" → elegir el **5** y abrir:
- **Calidad** y **Drift** (una captura);
- **Compuertas** (otra captura).

## 8. Prometheus: targets (`prometheus_01_targets`)

Navegador, `http://10.43.97.106:8009/targets`: todos los targets en **UP** (API, API de datos, cAdvisor de los dos nodos y Prometheus).

## 9. GitHub Actions (`cicd_07_actions_lista`)

GitHub → pestaña **Actions** del repo: la lista de corridas (`CI`, `Build Airflow`, `Build API`, `Build Streamlit`, `Build MLflow`) en verde.

Cuando estén, enviarlas a Cristhian (las guarda en `docs/images/` con esos nombres).
