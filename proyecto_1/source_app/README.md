# source_app: réplica local de la Data API

Copia de la Data API que expone el profesor (`http://10.43.97.110:8080`), con
el **mismo contrato y el mismo comportamiento**. Airflow la usa como
**respaldo**: siempre intenta primero el host remoto y solo si no responde lee
de aquí (ver `DATA_SOURCE_MODE` en `../airflow/README.md`).

> Recordatorio del enunciado: la entrega debe hacerse con la API del profesor.
> Esta réplica existe para cuando ese servicio no esté disponible y para hacer
> pruebas rápidas bajando el tiempo entre batches.

## Qué cambia respecto al código original

| Original                                   | source_app                                               |
|--------------------------------------------|----------------------------------------------------------|
| Lee `/data/covertype.csv` a memoria en cada arranque | La primera vez copia el CSV a la tabla `covertype` de Postgres (base `source_app`) y de ahí lee. |
| Estado por grupo en `/data/timestamps.json` | Estado en la tabla `group_state`; sobrevive a reinicios sin montar carpetas. |
| `MIN_UPDATE_TIME` fijo en el código         | Variable de entorno `MIN_UPDATE_TIME` (300 por defecto).  |
| `requirements.txt` + pip                    | `pyproject.toml` + uv.                                    |

La lógica se replica tal cual:

- El dataset se divide en 10 partes: `batch_size = total // 10` (58.101 filas).
- Cada petición a `/data` devuelve `batch_size // 10` filas (5.810) al azar.
- El batch del grupo avanza cuando pasaron más de `MIN_UPDATE_TIME` segundos
  desde el último cambio. El primero es el 1, y después del 11 responde `400`
  (`"Ya se recolectó toda la información minima necesaria"`).
- `/restart_data_generation` reinicia el temporizador y el conteo del grupo.
- **Igual que el original**, el rango de filas se calcula con el número de
  **grupo** y no con el de batch, así que un grupo siempre recibe filas del
  mismo rango (el grupo 1 las filas 58.102 a 116.202). Por la misma razón, los
  grupos 10 y 11 responden `500`, como en el original.

Una petición bloquea la fila del grupo (`SELECT ... FOR UPDATE`) para que dos
peticiones simultáneas no avancen el batch dos veces.

## Endpoints

| Método | Ruta                                       | Descripción                              |
|--------|--------------------------------------------|------------------------------------------|
| GET    | `/`                                        | Estado del servicio.                     |
| GET    | `/data?group_number=N`                     | Porción aleatoria del batch vigente.     |
| GET    | `/restart_data_generation?group_number=N`  | Reinicia el conteo del grupo.            |

```bash
curl "http://10.43.97.92:8012/data?group_number=1" | head -c 300
```

## Archivos

```
source_app/
├── Dockerfile          # python:3.12-slim + uv; el CSV viaja dentro de la imagen
├── docker-compose.yml  # servicio source-app (puerto 8012)
├── pyproject.toml
├── covertype.csv       # dataset completo (581.012 filas)
└── src/source_app/__init__.py
```

`diagram.py`, `project_2.png` y `python_command_history.py` vienen del
repositorio del profesor y no se usan en la imagen.

## Uso

Desde `proyecto_1/`:

```bash
docker compose up -d --build source-app
```

La primera vez tarda unos segundos más en quedar sana porque carga el CSV a
Postgres. Para pruebas rápidas:

```bash
MIN_UPDATE_TIME=20 docker compose up -d source-app
```
