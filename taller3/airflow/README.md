# Airflow

Todo lo relacionado con Airflow: su imagen, su base de datos de metadatos, sus
servicios y el DAG del taller.

> Esta carpeta **no se levanta sola**. El `docker-compose.yml` de `taller3/` la
> trae con `include:` y ahi viven la base de datos de datos (`postgres-data`) y
> la API. Siempre se ejecuta `docker compose up` desde `taller3/`.

## Servicios de este compose

| Servicio            | Contenedor                  | Puerto host | Para que sirve                                   |
|---------------------|-----------------------------|-------------|--------------------------------------------------|
| `postgres-airflow`  | `taller3-postgres-airflow`  | -           | **Solo** metadatos de Airflow                    |
| `airflow-init`      | `taller3-airflow-init`      | -           | Migra la base de metadatos y crea el usuario admin |
| `airflow-webserver` | `taller3-airflow-webserver` | **8026**    | UI de Airflow                                    |
| `airflow-scheduler` | `taller3-airflow-scheduler` | -           | Parsea y ejecuta el DAG                          |

UI en http://localhost:8026, o en http://10.43.97.92:8026 desde la red (mismo
puerto, solo cambia el host). Usuario `airflow` y clave `airflow`, definidos en
`.env`.

### Dos bases de datos separadas

- **`postgres-airflow`** (este archivo): estado interno de Airflow, sus DAG runs,
  tareas, XComs y conexiones. No publica puerto porque nadie tiene que entrar a
  mano; solo se conecta Airflow, por la red interna de compose.
- **`postgres-data`** (compose del root, puerto 8002): las tablas,
  `raw_penguins` y `clean_penguins`.

Airflow llega a la segunda a traves de una **conexion** que no hay que crear a
mano en la UI: se inyecta como variable de entorno.

```yaml
AIRFLOW_CONN_MLOPS_DATA: postgresql://postgres:admin123@postgres-data:5432/penguins
```

Airflow convierte cualquier variable `AIRFLOW_CONN_<NOMBRE>` en una conexion
llamada `<nombre>` en minusculas, asi que el DAG la usa como `mlops_data`
(definido en `dags/penguins/config.py` como `DATA_CONN_ID`).

### Por que LocalExecutor

El compose oficial de Airflow usa `CeleryExecutor`, que necesita ademas Redis,
un worker y un triggerer. Para este taller es peso muerto: con
`LocalExecutor` el propio scheduler ejecuta las tareas en procesos locales, son
tres contenedores menos y arranca mucho mas rapido. El DAG es identico en
ambos casos.

## La imagen (`Dockerfile`)

Se extiende la imagen oficial en lugar de usarla tal cual, por tres razones:

```dockerfile
FROM apache/airflow:2.10.5-python3.12

# 1. El volumen de modelos hereda de aqui el dueno correcto al crearse
RUN mkdir -p /opt/airflow/models && chown -R airflow:root ... && chmod -R 775 ...

# 2. Librerias que el DAG necesita y la imagen oficial no trae
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# 3. El CSV viaja dentro de la imagen: no hay que montar ninguna carpeta
COPY --chown=airflow:root data/penguins.csv /opt/airflow/data/penguins.csv
```

La alternativa era `_PIP_ADDITIONAL_REQUIREMENTS`, que instala las librerias al
arrancar **cada** contenedor, cada vez. El propio compose oficial advierte que
solo sirve para pruebas rapidas: construir la imagen una vez es mas sano.

Las versiones de `scikit-learn`, `numpy` y `joblib` en `requirements.txt` estan
fijadas a las mismas que usa la API (`../api/pyproject.toml`), para que los
`.pkl` se deserialicen sin advertencias de compatibilidad.

## Volumenes

Lo unico que se monta desde disco son los **DAGs**, porque son codigo que
queremos editar sin reconstruir la imagen. El resto son volumenes de Docker:

- **`airflow-logs-volume`**: los logs tienen que ser compartidos entre
  contenedores, porque las tareas corren en el *scheduler* pero quien los
  muestra en la UI es el *webserver*. Van a un volumen y no a una carpeta del
  repo para no ensuciar el working tree.
- **`models-volume`**: lo que produce el pipeline. Airflow escribe aqui y la API
  lo monta como `/models` en solo lectura. Se declara tambien en el compose del
  root, que es obligatorio: un archivo de compose que usa un volumen debe
  declararlo. Como las dos definiciones son identicas, `include` las fusiona en
  un unico volumen.

## El DAG

`dags/penguins_pipeline.py` define **un solo DAG con 4 tareas encadenadas**:

```
t1_borrar_datos -> t2_cargar_datos_crudos -> t3_preprocesar_datos -> t4_entrenar_modelos
```

Ese archivo solo arma el grafo: cada `PythonOperator` apunta a una funcion del
paquete `dags/penguins/`, donde esta el codigo real.

```
dags/
├── .airflowignore          # que el scheduler no escanee penguins/ buscando DAGs
├── penguins_pipeline.py    # solo el DAG
└── penguins/
    ├── config.py           # constantes: tablas, features, rutas
    ├── database.py         # PenguinsDatabase: todo el SQL
    ├── preprocessing.py    # PenguinsPreprocessor: crudos -> limpios
    ├── training.py         # ModelStore + entrenadores rf y gmm
    └── tasks.py            # las 4 funciones que ejecutan los operadores
```

El paquete vive dentro de `dags/` porque Airflow agrega esa carpeta al
`sys.path`, asi que `from penguins import tasks` funciona sin configurar nada.
El `.airflowignore` evita que el scheduler intente importar esos archivos
buscando DAGs.

### Las cuatro tareas

| Tarea                    | Funcion                  | Que hace                                          |
|--------------------------|--------------------------|---------------------------------------------------|
| `t1_borrar_datos`        | `tasks.borrar_datos`     | `DROP` + `CREATE` de las dos tablas: deja la base vacia. |
| `t2_cargar_datos_crudos` | `tasks.cargar_datos_crudos` | `COPY` del CSV a `raw_penguins` tal cual, todo `TEXT`, sin preprocesar. |
| `t3_preprocesar_datos`   | `tasks.preprocesar_datos` | Castea tipos, normaliza categoricas, descarta nulos y duplicados. |
| `t4_entrenar_modelos`    | `tasks.entrenar_modelos` | Lee `clean_penguins`, entrena `rf` y `gmm`, los guarda versionados. |

`training.py` se importa **dentro** de `entrenar_modelos()`, no al principio del
archivo, porque arrastra scikit-learn: asi el scheduler no lo carga cada vez que
parsea el DAG (lo hace cada 30 segundos).

### Los modelos

`ModelStore` busca el ultimo `vN.pkl` en `models/<tipo>/` y escribe el
siguiente, asi cada corrida deja una version nueva sin pisar las anteriores:

```
/opt/airflow/models/
├── rf/v1.pkl   v2.pkl ...
└── gmm/v1.pkl  v2.pkl ...
```

Los entrenadores heredan de `BaseTrainer`, que define el contrato: `train(df)`
devuelve `(payload, metricas)` y `run(df, store)` entrena, guarda y devuelve el
resumen que queda en XCom. Agregar un tercer modelo es una clase nueva y una
linea en `tasks.entrenar_modelos()`.