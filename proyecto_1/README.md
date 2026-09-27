# Proyecto 1 - Orquestación, entrenamiento y modelos (Nivel 1-2)

Entorno de MLOps completo con Docker Compose para predecir el **tipo de
cobertura forestal** (dataset *Covertype*, 7 clases) a partir de variables
cartográficas:

1. **Airflow** pide datos a la Data API del profesor cada 5 minutos, **una
   petición por ejecución del DAG**, y cada ejecución lleva esos datos por todo
   el proceso: crudo, procesado y listo para entrenamiento.
2. Cuando se completan los 10 batches, otro DAG entrena dos modelos (`rf` y
   `gmm`) y los guarda **versionados en MinIO**.
3. Una **API de inferencia** (FastAPI) lista los modelos de MinIO y predice con
   la versión que se le pida.

Si el host remoto no responde, Airflow usa `source_app`, una réplica local de
la Data API que sirve el mismo dataset desde Postgres.

## Estructura

Cada carpeta es un servicio independiente con su `docker-compose.yml` y su
README. El `docker-compose.yml` de esta carpeta los une en un solo proyecto con
`include`.

| Carpeta                              | Qué contiene                                                          |
|--------------------------------------|-----------------------------------------------------------------------|
| [`database/`](database/README.md)     | Instancia Postgres de datos con dos bases (`source_app`, `covertype`). |
| [`minio/`](minio/README.md)           | MinIO y un init que crea el bucket `models`.                          |
| [`source_app/`](source_app/README.md) | Réplica de la Data API del profesor, leyendo el CSV desde Postgres.   |
| [`airflow/`](airflow/README.md)       | Airflow con su propia instancia de Postgres y los dos DAGs.           |
| [`api/`](api/README.md)               | API de inferencia que consume los modelos de MinIO.                   |

Todo lo que es Python propio (`source_app`, `api`) se gestiona con **uv**
(`pyproject.toml`) y la imagen de Airflow instala sus dependencias con
`uv pip install`.

### Dos instancias de Postgres

- **`postgres-airflow`** (en `airflow/`): solo los metadatos de Airflow. No
  publica puerto.
- **`postgres-data`** (en `database/`, puerto 8015): los datos, con dos bases
  de datos y un usuario para cada una:
  - `source_app`: el dataset completo que sirve la réplica local.
  - `covertype`: lo que recolecta el DAG, en tres etapas (crudo, procesado y
    listo para entrenamiento).

## Servicios y puertos

El stack se despliega en la máquina virtual **10.43.97.92**:

| Servicio            | Puerto host | URL                                         | Credenciales             |
|---------------------|-------------|---------------------------------------------|--------------------------|
| UI de Airflow       | 8010        | http://10.43.97.92:8010                     | `airflow` / `airflow`    |
| API de inferencia   | 8011        | http://10.43.97.92:8011/docs                | -                        |
| source_app          | 8012        | http://10.43.97.92:8012/docs                | -                        |
| MinIO (API S3)      | 8013        | http://10.43.97.92:8013                     | `admin` / `admin123`     |
| Consola de MinIO    | 8014        | http://10.43.97.92:8014                     | `admin` / `admin123`     |
| Postgres de datos   | 8015        | `psql -h 10.43.97.92 -p 8015 -U postgres`   | `postgres` / `admin123`  |

Si el stack se levanta en otra máquina (por ejemplo para pruebas locales), se
cambia `10.43.97.92` por `localhost`; los puertos son los mismos.

## Cómo levantarlo

Siempre desde esta carpeta:

```bash
cd proyecto_1
docker compose up -d --build
```

Al arrancar, los DAGs quedan activos: la recolección empieza de inmediato
contra el host remoto (grupo 1).

Para apagar todo (y borrar volúmenes: datos, modelos y metadatos):

```bash
docker compose down -v
```

### Variables de configuración

Se pueden pasar por la línea de comandos o en un `.env` junto a cada compose:

| Variable                   | Por defecto                 | Para qué sirve                                                   |
|----------------------------|-----------------------------|------------------------------------------------------------------|
| `DATA_SOURCE_MODE`         | `auto`                      | `auto`: remoto y, si no responde, source_app. `remote` o `local` fuerzan uno. |
| `REMOTE_API_URL`           | `http://10.43.97.110:8080`  | Host remoto de la Data API.                                      |
| `GROUP_NUMBER`             | `1`                         | Grupo asignado.                                                  |
| `COLLECT_INTERVAL_SECONDS` | `300`                       | Cada cuánto corre el DAG de recolección.                         |
| `AUTO_RESTART_COLLECTION`  | `true`                      | Al terminar los batches, reinicia la generación y empieza otro ciclo. |
| `TRAIN_ONLY_IF_NO_MODEL`   | `true`                      | El entrenamiento automático solo crea modelos que aún no existen. |
| `MIN_UPDATE_TIME`          | `300`                       | Segundos por batch en source_app.                                |
