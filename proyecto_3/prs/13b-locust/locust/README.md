# Locust

`locustio/locust:2.46.7` con `locustfile.py` montado desde un ConfigMap. Corre en el nodo de datos para no quitarle CPU a la API, que está en el nodo de serving.

## Usuarios

| Clase | Peso | Qué envía |
|---|---|---|
| `PredictUser` | 4 | `POST /predict` con una fila de la muestra y `X-Traffic-Source: locust` |
| `ReplayUser` | 1 | `POST /predict` con una fila holdout, `X-Traffic-Source: replay` y `X-Replay-Row` con su `row_hash`; la vista `audit.replay_accuracy` la une con su precio real y da el MAPE en línea |

Los dos esperan entre 0,5 y 1,5 s entre peticiones. Una respuesta distinta de 200 cuenta como fallo (por ejemplo 503 si la API no tiene champion).

La muestra es `s3://datasets/replay/holdout_sample.json`, que el DAG actualiza en cada lote nuevo. Un init container la descarga con el usuario de MinIO `locust`, que solo puede leer `datasets/replay/*`. Si todavía no existe, el init container reintenta cada 30 s. Para usar una muestra más reciente basta con reiniciar el pod.

## Prueba por escalones

```bash
./locust/run_levels.sh                 # 10, 50, 100, 200 y 300 usuarios
./locust/run_levels.sh 10 50           # otros escalones
STABLE_SECONDS=120 ./locust/run_levels.sh
```

Por cada escalón corre Locust headless dentro del pod (rampa de 20 usuarios por segundo y 3 min estables), guarda `kubectl top` de los pods de la API y agrega una fila a `locust/resultados/resumen.csv` con RPS, fallos, latencias, si cumple (menos de 1 % de fallos y p95 menor a 500 ms), la versión champion y los segundos de inicio y fin para ubicar el escalón en Grafana. Antes de empezar comprueba que la API tenga champion.

La UI web queda en `http://10.43.97.106:8010` para pruebas manuales.
