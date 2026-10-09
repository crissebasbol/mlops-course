# MLflow

Servidor de tracking y Model Registry de MLflow, con su propia base de datos de
metadata. Es la misma configuración de `taller4/mlflow`, con nombres y puertos de
taller5.

## Servicios

| Servicio          | Contenedor                | Puerto host | Para qué sirve                                  |
|-------------------|---------------------------|-------------|-------------------------------------------------|
| `postgres-mlflow` | `taller5-postgres-mlflow` | -           | Metadata de MLflow (experimentos, runs, registry). No publica puerto. |
| `mlflow`          | `taller5-mlflow`          | 8004        | Servidor y UI de MLflow                         |

UI: http://10.43.97.105:8004