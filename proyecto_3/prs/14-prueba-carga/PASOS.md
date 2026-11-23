# Pasos del 23 nov: estado del pipeline, evidencias y prueba de carga

Todo se corre en la **.106** (`ssh estudiante@10.43.97.106`), desde el clon del repo de entrega. No hay que crear ramas ni hacer commits: solo mirar, capturar y correr la prueba de carga.

## 0. Preparar la terminal

```bash
cd ~/housing-price-mlops
git switch master && git pull
kubectl config current-context          # housing
./scripts/port_forward.sh status        # 8002 a 8011 deben estar en OK
```

Si algún puerto sale en FALLA: `./scripts/port_forward.sh start`.

## 1. Estado del pipeline

### 1.1 Qué modelo sirve la API y si hay sombra

```bash
curl -s http://10.43.97.106:8005/health; echo
```

| Campo | Qué significa |
|---|---|
| `champion_version` | Modelo que responde las predicciones (anoche quedó en 4) |
| `shadow_version` | `null`: no hay sombra. Un número: cada predicción corre también el challenger, y la API consume más CPU por petición. Anotarlo, porque cambia la capacidad en la prueba de carga |

### 1.2 Historia de los lotes

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "
SELECT ingestion_id AS ingreso, cycle AS ciclo, api_batch_number AS lote, outcome, final_status,
       training_code, promotion_decision, candidate_version AS candidata,
       round(mape_candidate::numeric, 4) AS mape_cand, round(mape_champion::numeric, 4) AS mape_champ,
       champion_version_after AS champion_despues
FROM audit.batch_runs ORDER BY ingestion_id"
```

Lo esperado:

| Ingreso | Ciclo | Lote | Resultado |
|---|---|---|---|
| 1 | 1 | 0 | Línea base rechazada por G6 (antes de recalibrarlo) |
| 2 | 1 | 1 | Línea base promovida (v2) |
| 3 | 1 | 2 | Entrena por señales, promovida (v3) |
| 4 | 1 | 3 | No entrena: lote pequeño |
| 5 | 1 | 4 | Entrena por drift, promovida (v4) |
| 6 | 1 | 5 | Entrena; promovida o rechazada según las compuertas |
| 7 | 1 | - | `end_of_data`: la API de datos se reinició |
| 8 en adelante | 2 | 0, 1, ... | `duplicate`: monitoreo del champion, sin reentrenar |

Si alguna fila tiene `final_status = failed`, revisar su `error` y avisar:

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "SELECT ingestion_id, error FROM audit.batch_runs WHERE final_status = 'failed'"
```

### 1.3 Recargas de la API

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "SELECT ts, action, from_version, to_version, actor FROM audit.model_actions ORDER BY ts"
```

Debe haber una fila `reload` por réplica cada vez que cambió el champion.

## 2. Capturas pendientes (antes de la carga)

Sin contraseñas ni tokens a la vista, y sin el aviso de "estás compartiendo pantalla".

| # | Dónde | Qué capturar |
|---|---|---|
| 1 | Argo (`https://10.43.97.106:8006`), app `airflow`, botón **History and Rollback** | Lista de sincronizaciones con su commit (por ejemplo `sha-6ad5b83`): evidencia de que un cambio en Git redespliega |
| 2 | Lo mismo en la app `serving` | Sincronizaciones de la API y de Streamlit |
| 3 | Argo, vista de árbol de `housing-root` | Las 4 apps (`data-platform`, `airflow`, `serving`, `observability`) en *Synced/Healthy* |
| 4 | Airflow (`:8002`), DAG `housing_pipeline`, vista **Grid** | Varias corridas con ramas distintas: promoción, rechazo, lote pequeño, fin de datos y duplicados |
| 5 | Airflow, una corrida de duplicado, vista **Graph** | La rama `monitor_production_model` tomada y el resto saltado |
| 6 | MLflow (`:8003`), **Models**, `housing-price-model` | Las versiones con sus alias (`champion`, `challenger`, `previous_champion`) |
| 7 | Streamlit (`:8007`), **Historial de lotes** | La tabla y las gráficas con el ciclo 1 completo y el ciclo 2 |

## 3. Prueba de carga (línea base, unos 20 minutos)

### 3.1 Antes de empezar

- Que la API tenga champion (paso 1.1). El script lo comprueba solo.
- Abrir Grafana (`http://10.43.97.106:8008`), dashboard **Housing API**, rango **Last 30 minutes** y refresco **10s**.
- No usar la UI web de Locust (`:8010`) durante la prueba: el script corre Locust aparte, dentro del pod.

### 3.2 Correr

Con `nohup` para que no se corte si se cae la sesión SSH:

```bash
cd ~/housing-price-mlops
nohup ./locust/run_levels.sh > locust/resultados_run.log 2>&1 &
tail -f locust/resultados_run.log        # Ctrl+C solo deja de mirar; la prueba sigue
```

Corre 5 escalones: **10, 50, 100, 200 y 300 usuarios**, cada uno con una rampa corta, 3 minutos estables y 30 s de descanso. Al empezar cada escalón el log muestra una línea `== rep2_uN: ...`.

### 3.3 Capturas durante la prueba

Al **final de cada escalón** (justo antes de que el log muestre el siguiente `==`), una captura de Grafana con estos paneles a la vista:

- Peticiones por segundo (total y por réplica).
- Latencia de `/predict` p50, p95 y p99.
- Tasa de error.
- CPU, memoria y throttling de los pods de la API.

Las más importantes son las de **100 y 300 usuarios**. Al terminar todo, una captura más del dashboard completo con los 5 escalones.

### 3.4 Al terminar

```bash
column -s, -t < locust/resultados/resumen.csv
ls locust/resultados/
kubectl -n housing-mlops top pod -l app=api
kubectl -n housing-mlops get pods -l app=api      # RESTARTS en 0 (sin OOM)
```

`resumen.csv` tiene una fila por escalón: RPS, peticiones, fallos, latencias p50, p95 y p99, y la columna `cumple` (menos de 1 % de fallos y p95 menor a 500 ms).

## 4. Qué enviar a Cristhian

1. La salida de los pasos 1.1, 1.2 y 1.3.
2. El contenido de `resumen.csv` (paso 3.4) y la salida de `kubectl top`.
3. Las capturas de la sección 2 y las de Grafana de la sección 3.

Con eso se escribe el análisis de carga del README: dónde se satura la API, por qué (CPU, throttling, sombra) y qué ajuste conviene. Si el ajuste es necesario, se repite un escalón para comparar antes y después.
