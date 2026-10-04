# MLflow

Servidor de tracking y Model Registry de MLflow, con su propia base de datos de
metadata.

## Servicios

| Servicio          | Contenedor                | Puerto host | Para qué sirve                                  |
|-------------------|---------------------------|-------------|-------------------------------------------------|
| `postgres-mlflow` | `taller4-postgres-mlflow` | -           | **Solo** metadata de MLflow (experimentos, runs, registry). No publica puerto. |
| `mlflow`          | `taller4-mlflow`          | 8016        | Servidor y UI de MLflow                         |

UI: http://10.43.97.92:8016

## Seguridad de hosts

- `MLFLOW_SERVER_ALLOWED_HOSTS="*"`: acepta cualquier `Host`.
- `MLFLOW_SERVER_CORS_ALLOWED_ORIGINS`: permite que la UI abierta desde
  `http://10.43.97.92:8016` haga cambios (por ejemplo mover un alias). Si se
  levanta en otra máquina se cambia con `MLFLOW_UI_ORIGIN`.