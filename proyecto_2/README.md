# Proyecto 2

Arquitectura MLOps completa desplegada en un clúster **RKE2 de dos nodos administrado con
Rancher**, para predecir la **readmisión hospitalaria de pacientes diabéticos**
(dataset *Diabetes 130-US hospitals 1999-2008*, 101.766 encuentros) en tres clases:

| Clase | `readmitted` | Significado |
|---|---|---|
| 0 | `NO` | No readmisión |
| 1 | `>30` | Readmisión tardía (más de 30 días) |
| 2 | `<30` | Readmisión temprana (menos de 30 días) |

Flujo:

1. **Airflow** carga el CSV por lotes de 15.000 filas (una ejecución del DAG = un lote) en
   la capa **raw**, valida calidad, limpia y guarda en **clean**, separa train/val/test,
   entrena 3 modelos, los registra en **MLflow** y promueve el mejor con el alias
   `champion`.
2. La **API** (FastAPI) sirve `diabetes_readmission@champion`, lo recarga sola cuando el
   alias cambia y registra cada inferencia en la capa **inference**.
3. **Streamlit** consume solo la API.
4. **Locust** genera carga contra la API desde otro nodo; **Prometheus** recolecta
   `/metrics` de cada réplica y CPU/memoria de los pods, y **Grafana** lo muestra.

## Arquitectura

![Arquitectura](images/Arquitectura.png)

| VM | IP | Rol |
|---|---|---|
| Instancia 1 (Fabián) | 10.43.97.106 | Rancher + puerta de entrada (no es nodo) |
| Instancia 2 (Cristian Organista) | 10.43.97.105 | Nodo etcd + control plane + worker: datos y entrenamiento |
| Instancia 3 (Cristhian Bolaños) | 10.43.97.92 | Nodo worker: inferencia y observabilidad |

## Estructura

| Carpeta | Contenido |
|---|---|
| [`cluster/`](cluster/README.md) | Pasos en las VMs: Rancher, clúster RKE2, `local-path`, labels |
| [`database/`](database/README.md) | `postgres-data` (StatefulSet) y scripts de creación de schemas/tablas |
| [`minio/`](minio/README.md) | MinIO (StatefulSet) y Job que crea los buckets `mlflows3` y `datasets` |
| [`mlflow/`](mlflow/README.md) | Imagen y Deployment de MLflow + `postgres-mlflow` |
| [`airflow/`](airflow/README.md) | Imagen con el DAG, `values.yaml` de Helm, `postgres-airflow` |
| [`api/`](api/README.md) | API de inferencia (FastAPI, uv) |
| [`streamlit/`](streamlit/README.md) | Interfaz gráfica |
| [`locust/`](locust/README.md) | Imagen de Locust, escenario y `run_levels.sh` |
| [`observability/`](observability/README.md) | Prometheus (RBAC, configuración) y Grafana (provisioning + dashboard JSON) |
| [`notebooks/`](notebooks/eda.ipynb) | Análisis exploratorio y justificación de la limpieza |
| [`scripts/`](scripts) | `build_push.sh`, `deploy.sh`, `port_forward.sh` |

Cada componente tiene un `kustomization.yaml`; el de esta carpeta los une, así todo
(menos Airflow, que va con Helm) se aplica con `kubectl apply -k .`.

Todos los contenedores definen `resources.requests/limits`; además un `LimitRange` en el
namespace cubre los init containers del chart de Airflow.

## Imágenes en Docker Hub

| Imagen | Contenido |
|---|---|
| `crissebasbol/proyecto2-airflow:1.0.0` | `apache/airflow:3.1.8` + DAG + dependencias de ML |
| `crissebasbol/proyecto2-mlflow:1.0.0` | MLflow 3.16.1 con soporte Postgres y S3 |
| `crissebasbol/proyecto2-api:1.0.0` | API FastAPI |
| `crissebasbol/proyecto2-streamlit:1.0.0` | Interfaz Streamlit |
| `crissebasbol/proyecto2-locust:1.0.0` | Locust con el escenario de `/predict` |

## Servicios y puertos

Solo los puertos 8000-8025 están abiertos hacia afuera, así que las UIs se publican con
`kubectl port-forward` desde `10.43.97.106` (`scripts/port_forward.sh`). Dentro del clúster
todos los servicios son `ClusterIP`.

| Servicio | URL | Credenciales |
|---|---|---|
| Rancher | https://10.43.97.106:8001 | `admin` / la definida al instalar |
| Airflow | http://10.43.97.106:8002 | `admin` / `admin` |
| MLflow | http://10.43.97.106:8003 | - |
| Consola MinIO | http://10.43.97.106:8004 | `admin` / `admin123` |
| API (docs) | http://10.43.97.106:8005/docs | - |
| Streamlit | http://10.43.97.106:8007 | - |
| Grafana | http://10.43.97.106:8008 | `admin` / `admin` |
| Prometheus | http://10.43.97.106:8009 | - |
| Locust | http://10.43.97.106:8010 | - |

`kubectl port-forward` a un Service se conecta a **un solo pod**. Para probar balanceo y
carga se usa Locust **dentro del clúster** (llama a `http://api:8000`, que sí reparte entre
réplicas).

## Despliegue paso a paso

### 1. Construir y publicar las imágenes

```bash
docker login
cd proyecto_2
./scripts/build_push.sh 1.0.0
```

Por defecto construye `linux/amd64` (la arquitectura de las VMs). Para un componente:
`./scripts/build_push.sh 1.0.1 api` (y actualizar el tag en su `k8s/deployment.yaml`).

### 2. Preparar el clúster

Seguir [cluster/README.md](cluster/README.md) (Rancher en `.106`, nodos `.105` y `.92`,
`local-path` como StorageClass por defecto y labels `mlops/tier`).

### 3. Desplegar (en 10.43.97.106)

```bash
git clone <repo> && cd mlops-course/proyecto_2
./scripts/deploy.sh
```

`deploy.sh` aplica los manifiestos, espera a que bases de datos, MinIO y MLflow estén listos
e instala Airflow con Helm:

```bash
helm upgrade --install airflow apache-airflow/airflow -n proyecto2 -f airflow/values.yaml --wait --timeout 20m
```

Verificar:

```bash
kubectl -n proyecto2 get pods -o wide        # columna NODE: data vs serving
kubectl -n proyecto2 get pvc
helm list -n proyecto2
```

### 4. Publicar las UIs

```bash
./scripts/port_forward.sh start
./scripts/port_forward.sh status
```

### 5. Ejecutar el DAG

El DAG `diabetes_pipeline` arranca activo y corre cada 10 minutos (también se puede
disparar a mano en la UI). Cada ejecución procesa un lote: con 101.766 filas son **7
ejecuciones**. En la primera, `t01` descarga el CSV a MinIO (`datasets/source/Diabetes.csv`).
Cuando ya no quedan lotes, `hay_lote_nuevo` salta el resto de tareas (no reentrena sin
datos nuevos).

```text
t01_validar_fuente >> t02_cargar_lote_raw >> hay_lote_nuevo >> t03_validar_calidad
  >> t04_preprocesar >> t05_guardar_clean >> t06_split
  >> [t07_entrenar_logistic_regression, t07_entrenar_random_forest, t07_entrenar_hist_gradient_boosting]
  >> t08_registrar_mlflow >> t09_comparar >> t10_promover
```

Revisar los datos:

```bash
kubectl -n proyecto2 exec -it postgres-data-0 -- psql -U postgres -d diabetes
```

```sql
SELECT batch_id, row_start, row_end, rows_inserted, rows_valid, rows_rejected, rows_clean, status FROM raw.batches ORDER BY batch_id;
SELECT status, count(*) FROM raw.diabetes GROUP BY status;
SELECT split, readmitted, count(*) FROM clean.diabetes GROUP BY 1, 2 ORDER BY 1, 2;
SELECT created_at, prediction_label, probability, model_version, latency_ms FROM inference.predictions ORDER BY created_at DESC LIMIT 10;
```

### 6. Probar la API

```bash
curl http://10.43.97.106:8005/health
curl http://10.43.97.106:8005/model-info
curl -X POST http://10.43.97.106:8005/predict -H 'Content-Type: application/json' \
  -d @<(python3 -c "import json; print(json.dumps(json.load(open('streamlit/examples.json'))['<30'][0]))")
```

### 7. Prueba de carga

UI de Locust en http://10.43.97.106:8010, o por niveles en modo headless (desde `.106`):

```bash
cd locust
./run_levels.sh 10 30 60 100 150 200 300
```

Cada nivel tiene rampa + 2 minutos estables y se anota en `locust/resultados/resumen.csv`
con usuarios, spawn rate, peticiones, exitosas, fallidas, latencia promedio, p50/p95/p99 y si
**cumple** el criterio (menos de 1 % de fallos y p95 menor a 500 ms, el mismo de taller_5).
El punto de degradación es el primer nivel que no cumple. Mientras corre, el dashboard de
Grafana (http://10.43.97.106:8008) muestra el efecto.

Para comparar con más réplicas:

```bash
kubectl -n proyecto2 scale deployment api --replicas=3
```

## Decisiones técnicas

### Capas de datos

Una instancia `postgres-data` con la base `diabetes` y tres **schemas** con dueños distintos:

| Schema | Escribe | Lee |
|---|---|---|
| `raw` | `airflow_etl` | `airflow_etl` |
| `clean` | `airflow_etl` | `airflow_etl` |
| `inference` | `api_writer` | `api_writer`, `airflow_etl` (para futuros reentrenamientos) |

La separación es lógica y de permisos (la API no puede tocar raw/clean y Airflow no puede
escribir inferencias)

`raw.diabetes` guarda las 50 columnas como texto, sin transformar, más `row_hash` (PK),
`batch_id`, `load_timestamp`, `source_file`, `source_row`, `status` y `status_reason`.
`raw.batches` lleva el control de cada lote.

### Limpieza y features

Documentadas en [notebooks/eda.ipynb](notebooks/eda.ipynb). En resumen: se eliminan `weight`,
`payer_code` e IDs; se excluyen encuentros de pacientes fallecidos o en hospicio; los IDs de
admisión/alta/origen y la especialidad se agrupan; los diagnósticos ICD-9 se agrupan en 9
categorías; de 23 medicamentos se conservan 7 y se crean `diabetes_meds_active` y
`diabetes_meds_changed`. El split es **por paciente** (hash de `patient_nbr`, 70/15/15), estable
entre ejecuciones y sin fuga entre train y test.

### Modelos y métrica

Se entrenan en paralelo `LogisticRegression`, `RandomForestClassifier` y
`HistGradientBoostingClassifier`, todos con pesos balanceados. **Métrica de selección: F1
macro en validación**, porque da el mismo peso a las tres clases y la readmisión temprana
(~11 %) es la más relevante clínicamente; accuracy premiaría predecir siempre `NO`. Se registran
también F1 y recall por clase, F1 weighted, ROC-AUC OvR, matriz de confusión y reporte de
clasificación.

`t09` (Airflow) re-evalúa el `champion` vigente sobre el **mismo** split de validación actual y `t10`
solo lo reemplaza si el mejor candidato lo supera. El mejor candidato de cada ejecución queda
con el alias `challenger`.

### Carga del modelo en la API

El modelo se carga al arrancar y un hilo consulta el alias `champion` cada 60 s
(`MODEL_REFRESH_SECONDS`); solo descarga de MLflow cuando la versión cambió. `/predict` nunca
llama a MLflow, y un nuevo champion entra sin redeploy. `POST /reload` fuerza la revisión.
Mientras no exista un champion, `/predict` responde 503 y `/model-info` lo explica.

### Métricas expuestas por la API

| Métrica | Tipo |
|---|---|
| `http_requests_total{method,endpoint,status}` | Counter |
| `http_request_duration_seconds{method,endpoint}` | Histogram |
| `http_requests_in_progress` | Gauge |
| `predictions_total{prediction_label,model_version}` | Counter |
| `prediction_errors_total{reason}` | Counter |
| `model_inference_duration_seconds` | Histogram |
| `inference_log_duration_seconds` | Histogram |
| `model_info{model_name,model_version,alias}` | Gauge |
| `process_cpu_seconds_total`, `process_resident_memory_bytes` | automáticas |

El dashboard **Proyecto 2 - API de inferencia** (`observability/grafana/dashboards/proyecto2-api.json`)
tiene total de solicitudes, RPS, latencia promedio, p50/p95/p99, errores, tasa de error, CPU,
memoria y throttling por pod (cAdvisor), predicciones por clase, tiempo del modelo vs tiempo del
insert en Postgres y versión del modelo activa.

## Evidencias

Las capturas van en [`images/`](images).