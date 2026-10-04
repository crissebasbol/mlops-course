# Base de datos de datos (`postgres-data`)

Instancia de Postgres 16 donde viven **los datos** del taller: los crudos y los
procesados. Es distinta de la base de metadata de MLflow (`postgres-mlflow`,
en `../mlflow/`), como pide el enunciado.

## Servicios

| Servicio        | Contenedor              | Puerto host | Para qué sirve                    |
|-----------------|-------------------------|-------------|-----------------------------------|
| `postgres-data` | `taller4-postgres-data` | 8021        | Postgres con la base `covertype`  |

Superusuario: `postgres` / `admin123`.

## Base de datos `covertype`

`init/01-create-database.sh` la crea la primera vez que arranca el contenedor
(cuando el volumen está vacío), con su propio usuario: `covertype` /
`covertype123`. Es el usuario que usa el notebook.

## Tablas

Las crea y llena el notebook `../jupyter/notebooks/covertype_mlflow.ipynb`. Antes
de cargar valida lo que ya existe:

- `raw_covertype` solo se recarga si no existe o no tiene las mismas filas que
  el CSV (por ejemplo, después de una carga interrumpida).
- `clean_covertype` solo se reprocesa si raw se acaba de recargar o si no existe
  o está vacía.
- Con `FORCE_RELOAD = True` en el notebook se recargan las dos.

Cuando hay que cargar, la tabla se recrea completa, así que nunca quedan filas
duplicadas.

| Tabla             | Etapa       | Contenido                                                                 |
|-------------------|-------------|---------------------------------------------------------------------------|
| `raw_covertype`   | Sin procesar| Las 581.012 filas del CSV tal cual (`TEXT`), con `id` y `loaded_at`.       |
| `clean_covertype` | Procesada   | Numéricas como `DOUBLE PRECISION`, `cover_type` entero, sin nulos ni duplicados, con su `split` (`train` / `test`). |