# Taller 3 - Airflow + Postgres + API de inferencia

Pipeline de ML orquestado con Airflow: carga los datos de Penguins a una base de
datos, los preprocesa, entrena modelos y los deja disponibles para una API de
inferencia.

Los servicios estan repartidos en dos archivos que compose une en **un solo
proyecto** con `include`:

- `airflow/docker-compose.yml` - todo lo de Airflow (su base de metadatos, init,
  webserver y scheduler).
- `docker-compose.yml` (raiz de `taller3/`) - la base de datos de datos y la API,
  y trae el anterior con:

```yaml
include:
  - airflow/docker-compose.yml
```

Por eso basta un `docker compose up` desde `taller3/` para levantar todo, y los
servicios se ven entre si por nombre aunque esten en archivos distintos.

Cada carpeta tiene su propio detalle: [`airflow/README.md`](airflow/README.md)
para el DAG y la instancia de Airflow, [`api/README.md`](api/README.md) para el
servicio de inferencia.

## Servicios

| Servicio           | Definido en                  | Puerto host | Para que sirve                                   |
|--------------------|------------------------------|-------------|--------------------------------------------------|
| `postgres-data`    | `docker-compose.yml`         | **8002**    | Datos: `raw_penguins` y `clean_penguins`         |
| `api`              | `docker-compose.yml`         | **8024**    | API de inferencia (FastAPI)                      |
| `postgres-airflow` | `airflow/docker-compose.yml` | -           | **Solo** metadatos de Airflow (red interna)      |
| `airflow-init`     | `airflow/docker-compose.yml` | -           | Migra la BD de metadatos y crea el usuario admin |
| `airflow-webserver`| `airflow/docker-compose.yml` | **8023**    | UI de Airflow                                    |
| `airflow-scheduler`| `airflow/docker-compose.yml` | -           | Ejecuta el DAG (LocalExecutor)                   |

Volumenes:

- `data-db-volume` - datos de `postgres-data`
- `airflow-db-volume` - metadatos de `postgres-airflow`
- `airflow-logs-volume` - logs de las tareas. Van a un volumen y no a una carpeta
  del repo, pero tienen que ser compartidos: las tareas corren en el scheduler y
  la UI que los muestra vive en el webserver.
- `models-volume` - modelos entrenados; Airflow escribe (`/opt/airflow/models`)
  y la API lee en solo lectura (`/models`)

Lo unico que se monta desde disco es `airflow/dags`, el codigo que editamos.
El CSV no se monta: viaja dentro de la imagen de Airflow (`COPY` en su
Dockerfile), porque es un archivo fijo. Si se cambia, hay que reconstruir con
`docker compose build`.

## Como levantarlo

Siempre desde la raiz de `taller3/`, nunca desde `airflow/` (ese compose por si
solo no incluye la base de datos de datos ni la API):

```bash
cd taller3
docker compose up -d --build
```

Servicios disponibles:

| Servicio          | En la maquina que levanta el stack | Desde la red                  |
|-------------------|------------------------------------|-------------------------------|
| UI de Airflow     | http://localhost:8023              | http://10.43.97.92:8023        |
| API de inferencia | http://localhost:8024/docs         | http://10.43.97.92:8024/docs   |
| Postgres de datos | `localhost:8002`                   | `10.43.97.92:8002`             |

Los puertos son los mismos del `docker-compose.yml`: lo unico que cambia es el
host. Si el stack corre en el servidor del curso, se prueba contra
**10.43.97.92** con esos mismos puertos.

Credenciales: Airflow con usuario `airflow` y clave `airflow`; Postgres con
`psql -h 10.43.97.92 -p 8002 -U postgres -d penguins` y clave `admin123`.

El DAG esta configurado con `schedule_interval="@once"`, asi que se ejecuta
solo la primera vez que Airflow lo detecta. Para volver a correrlo: entrar a la
UI, abrir `penguins_training_pipeline` y darle **Trigger DAG**. Tambien se puede
desde la linea de comandos:

```bash
docker compose exec airflow-scheduler airflow dags trigger penguins_training_pipeline
```

Para apagar todo (y borrar los volumenes):

```bash
docker compose down -v
```

## El DAG: `penguins_training_pipeline`

Definido en `airflow/dags/penguins_pipeline.py`. Es **un solo DAG con 4 tareas
encadenadas**, una por cada punto del taller:

```
t1_borrar_datos -> t2_cargar_datos_crudos -> t3_preprocesar_datos -> t4_entrenar_modelos
```

| Tarea                    | Que hace                                                                     |
|--------------------------|------------------------------------------------------------------------------|
| `t1_borrar_datos`        | **Borra el contenido de la base de datos**: elimina y vuelve a crear `raw_penguins` (todo `TEXT`) y `clean_penguins` (tipada). |
| `t2_cargar_datos_crudos` | `COPY` del CSV a `raw_penguins` tal cual, **sin ningun preprocesamiento**.   |
| `t3_preprocesar_datos`   | Castea tipos, normaliza categoricas, descarta nulos y duplicados, y escribe en `clean_penguins`. |
| `t4_entrenar_modelos`    | Lee `clean_penguins` y entrena los modelos: `rf` (el mejor de 3 clasificadores) y `gmm`, guardados como `models/rf/vN.pkl` y `models/gmm/vN.pkl`. |

Cada tarea es un `PythonOperator`. El archivo del DAG solo arma el grafo y
encadena con `t1 >> t2 >> t3 >> t4`; el codigo real vive en el paquete
`airflow/dags/penguins/`:

| Archivo            | Contenido                                                        |
|--------------------|------------------------------------------------------------------|
| `config.py`        | Constantes: tablas, features, rutas, parametros de entrenamiento. |
| `database.py`      | `PenguinsDatabase`: todo el SQL contra `postgres-data` (crear y borrar tablas, `COPY` del CSV, leer y escribir DataFrames). |
| `preprocessing.py` | `PenguinsPreprocessor`: casteo de tipos, normalizacion de categoricas y descarte de filas invalidas. |
| `training.py`      | `ModelType`, `ModelStore` (versionado `vN.pkl`) y los entrenadores `RandomForestTrainer` y `GaussianMixtureTrainer`, ambos sobre `BaseTrainer`. |
| `tasks.py`         | Las cuatro funciones que ejecutan los operadores. Solo coordinan. |

El paquete esta dentro de `dags/` porque Airflow agrega esa carpeta al
`sys.path`, y un `.airflowignore` evita que el scheduler lo escanee buscando
DAGs.

### Tablas

`raw_penguins` guarda el CSV sin tocar (todas las columnas `TEXT`, los faltantes
quedan como el literal `'NA'`, tal como vienen en el archivo):

```sql
rowid, species, island, bill_length_mm, bill_depth_mm,
flipper_length_mm, body_mass_g, sex, year, ingested_at
```

`clean_penguins` guarda el resultado del preprocesamiento, ya tipado y sin
nulos:

```sql
id, species, island, sex,
bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g,
year, processed_at
```

De las 344 filas del CSV se descartan las 11 que tienen medidas o sexo
faltante, quedando 333 para entrenamiento.

### Versionado de modelos

Cada ejecucion del DAG crea una version nueva: el codigo busca el ultimo
`vN.pkl` dentro de `models/<tipo>/` y escribe `v(N+1).pkl`. Nada se sobrescribe,
y la API puede servir cualquier version anterior.

## API de inferencia

Detalle completo en `api/README.md`. Resumen:

| Metodo | Ruta       | Descripcion                                       |
|--------|------------|---------------------------------------------------|
| GET    | `/health`  | Estado del servicio.                              |
| GET    | `/models`  | Modelos disponibles por tipo con sus versiones.   |
| POST   | `/predict` | Predice la especie con el modelo y version dados. |

```bash
# Desde la maquina que levanta el stack; desde la red, cambiar
# localhost por 10.43.97.92 (el puerto es el mismo).
curl -X POST http://localhost:8024/predict \
  -H "Content-Type: application/json" \
  -d '{
    "bill_length_mm": 39.1,
    "bill_depth_mm": 18.7,
    "flipper_length_mm": 181.0,
    "body_mass_g": 3750.0,
    "island": "Torgersen",
    "sex": "male",
    "model_type": "rf"
  }'
```

Si se omite `version` se usa la ultima disponible. Mientras el DAG no se haya
ejecutado no hay modelos y `/predict` responde `404`.

## Consultar la base de datos

```bash
# Filas crudas y limpias
docker compose exec postgres-data \
  psql -U postgres -d penguins -c "SELECT count(*) FROM raw_penguins;"

docker compose exec postgres-data \
  psql -U postgres -d penguins -c "SELECT * FROM clean_penguins LIMIT 5;"
```