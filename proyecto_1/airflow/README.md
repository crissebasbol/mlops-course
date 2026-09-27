# Airflow

Orquestador del proyecto: su imagen, su base de datos de metadatos, sus
servicios y los dos DAGs.

## Servicios de este compose

| Servicio            | Contenedor                    | Puerto host | Para qué sirve                                     |
|---------------------|-------------------------------|-------------|----------------------------------------------------|
| `postgres-airflow`  | `proyecto1-postgres-airflow`  | -           | **Solo** metadatos de Airflow                      |
| `airflow-init`      | `proyecto1-airflow-init`      | -           | Migra la base de metadatos y crea el usuario admin |
| `airflow-webserver` | `proyecto1-airflow-webserver` | 8010        | UI de Airflow                                      |
| `airflow-scheduler` | `proyecto1-airflow-scheduler` | -           | Parsea y ejecuta los DAGs (LocalExecutor)          |

UI en http://10.43.97.92:8010, usuario `airflow` y clave `airflow` (en `.env`).

Airflow llega a la base de datos `covertype` de `postgres-data` con una
conexión que se inyecta como variable de entorno, sin crearla a mano:

```yaml
AIRFLOW_CONN_COVERTYPE_DATA: postgresql://covertype:covertype123@postgres-data:5432/covertype
```

Los DAGs la usan como `covertype_data` (`DATA_CONN_ID` en `config.py`).

## Los DAGs

```
dags/
├── .airflowignore               # el scheduler no escanea covertype/ buscando DAGs
├── covertype_collection.py      # DAG de recolección
├── covertype_training.py        # DAG de entrenamiento
└── covertype/
    ├── config.py                # variables de entorno, tablas, features, parámetros
    ├── source_client.py         # DataSourceClient: remoto o source_app
    ├── database.py              # CovertypeDatabase: todo el SQL
    ├── preprocessing.py         # CovertypePreprocessor: crudo -> procesado
    ├── storage.py               # ModelRegistry: modelos versionados en MinIO
    ├── training.py              # entrenadores rf y gmm
    └── tasks.py                 # las funciones que ejecutan los operadores
```

### 1. `covertype_data_collection`

Corre cada 5 minutos (`COLLECT_INTERVAL_SECONDS`), con `catchup=False` y
`max_active_runs=1`. **Cada ejecución hace una sola petición a `/data` y la
lleva por todo el proceso**, como pide el enunciado:

| Tarea                       | Qué hace                                                                     |
|-----------------------------|------------------------------------------------------------------------------|
| `t1_resolver_fuente`        | Consulta `GET /` del host remoto (timeout de 5 s). Si responde, se usa el remoto; si no, `source_app`. |
| `t2_obtener_datos`          | Una petición a `/data?group_number=1`. Guarda las filas en `raw_covertype` sin duplicados y registra la petición en `collection_log`. |
| `t3_preprocesar_datos`      | Lee las filas crudas pendientes, las tipa y valida, y las escribe en `clean_covertype`. |
| `t4_preparar_entrenamiento` | Pasa las filas completas a `train_covertype` con su split `train`/`test`.     |
| `t5_ciclo_completo`         | `ShortCircuit`: sigue solo si esta ejecución completó los 10 batches del ciclo. |
| `t6_publicar_dataset`       | Su `outlet` actualiza el Dataset `train_covertype`, que dispara el DAG de entrenamiento. |

**Fuente de datos** (`DATA_SOURCE_MODE`):

| Valor    | Comportamiento                                              |
|----------|-------------------------------------------------------------|
| `auto`   | Primero el host remoto (`REMOTE_API_URL`); si no responde, `source_app`. |
| `remote` | Solo el remoto (falla si no responde).                      |
| `local`  | Solo `source_app`. Útil para pruebas sin tocar el conteo del grupo en el servidor del profesor. |

**Ciclos**: `collection_log` lleva, por fuente, en qué ciclo va la recolección
y qué batches ya se recibieron. Cuando la API responde `400` (ya entregó todos
los batches), con `AUTO_RESTART_COLLECTION=true` se llama a
`/restart_data_generation` y empieza un ciclo nuevo. En esa ejecución no se
vuelve a pedir `/data`; la siguiente trae el primer batch del ciclo nuevo.

Como el batch cambia cada 5 minutos y el DAG corre cada 5 minutos, a veces dos
ejecuciones seguidas reciben el mismo batch. No pasa nada: las filas repetidas
no se insertan (`ON CONFLICT DO NOTHING` sobre `row_hash`) y el ciclo solo se
completa cuando hay 10 batches **distintos**.

**Preprocesamiento** (`preprocessing.py`):

- Numéricas a `float` (`DOUBLE PRECISION` en la base). Lo que no es número
  queda en `NULL`.
- `Wilderness_Area` al nombre canónico (`Rawah`, `Neota`, `Commanche`,
  `Cache`); `Soil_Type` en mayúsculas con formato `C####`.
- `Cover_Type` entre 0 y 6; sin etiqueta válida la fila se descarta.
- La etapa de entrenamiento solo toma filas sin `NULL`. El split sale del hash
  de la fila (80/20), así una fila queda siempre del mismo lado entre versiones
  de modelos.

### 2. `covertype_model_training`

```
decidir_entrenamiento -> entrenar_rf
                      -> entrenar_gmm
```

Dos formas de dispararlo:

| Trigger                                  | Qué entrena                                                          |
|------------------------------------------|----------------------------------------------------------------------|
| Automático (Dataset `train_covertype`)   | Con `TRAIN_ONLY_IF_NO_MODEL=true`, solo los tipos que aún no tienen ninguna versión en MinIO. Si ya existen, las dos tareas quedan en *skipped*. |
| Manual (botón *Trigger DAG*)             | Siempre `rf` y `gmm`.                                                |

Con esto el entrenamiento automático no llena el disco con un modelo por
ciclo; para reentrenar con los datos acumulados se usa el trigger manual.

**Modelos** (`training.py`):

| Tipo  | Modelo                                                   | Métricas en `metadata.json`                  |
|-------|----------------------------------------------------------|----------------------------------------------|
| `rf`  | `RandomForestClassifier` (100 árboles, profundidad máx. 25) sobre numéricas + one-hot de `wilderness_area` y `soil_type` | `accuracy`, `f1_macro` sobre test |
| `gmm` | `GaussianMixture` de 7 componentes sobre numéricas escaladas; cada cluster se etiqueta con el `cover_type` mayoritario | `accuracy` sobre test, `silhouette` (muestra de 5.000), `adjusted_rand_index` |

**Versionado**: cada entrenamiento sube `models/<tipo>/v<N+1>/` a MinIO con el
modelo y su `metadata.json`. Nada se sobrescribe.