# Base de datos de datos (`postgres-data`)

Instancia de Postgres 16 donde viven **los datos** del proyecto. Los
metadatos de Airflow van en otra instancia (`postgres-airflow`, en
`../airflow/`).

## Servicios

| Servicio        | Contenedor                | Puerto host | Para qué sirve                          |
|-----------------|---------------------------|-------------|-----------------------------------------|
| `postgres-data` | `proyecto1-postgres-data` | 8015        | Postgres con las dos bases de datos     |

## Dos bases de datos, un usuario para cada una

`init/01-create-databases.sh` las crea la primera vez que arranca el
contenedor (cuando el volumen está vacío):

| Base de datos | Usuario / clave              | La usa       | Contenido                                     |
|---------------|------------------------------|--------------|-----------------------------------------------|
| `source_app`  | `source_app` / `source_app123` | source_app | El dataset completo y el estado por grupo     |
| `covertype`   | `covertype` / `covertype123`   | Airflow    | Datos recolectados en tres etapas + log       |

Superusuario: `postgres` / `admin123`.

## Tablas

### `source_app`

| Tabla         | Contenido                                                                 |
|---------------|---------------------------------------------------------------------------|
| `covertype`   | Las 581k filas del CSV, todo `TEXT`, con un `id` en el orden del archivo. |
| `group_state` | Por grupo: timestamp del último cambio de batch y batch actual.           |

### `covertype`

| Tabla             | Etapa                    | Contenido                                                          |
|-------------------|--------------------------|--------------------------------------------------------------------|
| `raw_covertype`   | Sin procesar             | Las filas tal cual llegan de la API (`TEXT`), con fuente, ciclo, batch y `dag_run_id`. |
| `clean_covertype` | Procesada                | Tipada y validada: numéricas como `DOUBLE PRECISION`; lo que no es número queda en `NULL`. |
| `train_covertype` | Lista para entrenamiento | Solo filas completas, con su `split` (`train` o `test`).           |
| `collection_log`  | Control                  | Una fila por petición: fuente, ciclo, batch, estado, filas recibidas y nuevas. |

Las tres etapas usan como llave primaria `row_hash`, el md5 de los valores
crudos de la fila. Así, **una fila repetida entre peticiones no se duplica**:
se inserta con `ON CONFLICT DO NOTHING`. Después de muchas peticiones la base
deja de crecer porque ya tiene todas las filas que puede entregar la API.