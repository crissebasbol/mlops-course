# Pasos del 23 nov (noche): autoescalado de la API y segunda prueba de carga

Todo se corre en la **.106** (`ssh estudiante@10.43.97.106`), desde el clon del repo de entrega.

Contexto:
- **Antes:** la primera prueba con `run_levels.sh` (2 réplicas fijas, sombra al 20 %) se estancó en unos 8 RPS, 4 por réplica, con la CPU de cada réplica en su límite. Ya está en las capturas `locust_04` a `grafana_06`.
- **Ahora:** el PR `feature/hpa-api` agrega un HPA que mantiene la API entre 2 y 3 réplicas según la CPU. Esta segunda prueba mide si la capacidad crece cuando el HPA escala.

**Límite:** el PR se fusiona antes del **lunes 23 a las 23:59**.

## 1. Fusionar el PR `feature/hpa-api`

En GitHub: aprobar y fusionar con **Create a merge commit**. No cambia imágenes (no hay build), así que Argo lo aplica en la siguiente sincronización.

Al aplicarlo, el Deployment deja de fijar `replicas`. Puede bajar un momento a 1 réplica, y el HPA lo sube a 2 en unos segundos. Es normal.

```bash
cd ~/housing-price-mlops && git switch master && git pull
argocd app get serving --refresh | tail -10           # debe aparecer HorizontalPodAutoscaler api
kubectl -n housing-mlops get hpa api                  # TARGETS con un porcentaje (no <unknown>), MINPODS 2, MAXPODS 3
kubectl -n housing-mlops get pods -l app=api          # 2 réplicas Running
```

Si `TARGETS` dice `<unknown>` por más de un minuto, enviar la salida de `kubectl -n housing-mlops describe hpa api | tail -15`.

**Captura:** el `argocd app get serving` con el HPA y el `get hpa`.

## 2. Segunda prueba de carga (unos 15 minutos)

Grafana (`http://10.43.97.106:8008`), dashboard **Housing API**, rango **Last 30 minutes**, refresco **10s**. No usar la UI web de Locust (`:8010`).

**Terminal 1**, la prueba:

```bash
cd ~/housing-price-mlops
nohup ./locust/run_levels.sh 10 25 50 100 > locust/resultados_run2.log 2>&1 &
tail -f locust/resultados_run2.log
```

**Terminal 2**, el HPA en vivo:

```bash
kubectl -n housing-mlops get hpa api -w
```

Debe pasar de 2 a 3 réplicas cuando la CPU supere el 70 %, y volver a 2 unos 3 minutos después de terminar.

### Capturas

- Terminal 2 cuando el HPA sube a 3 réplicas (columnas `TARGETS` y `REPLICAS`).
- Al **final de cada escalón**, Grafana con:
  - peticiones por segundo (total y por réplica, donde debe aparecer la tercera);
  - "Réplicas de la API arriba";
  - latencia de `/predict` p50, p95 y p99;
  - peticiones en curso;
  - CPU, memoria y throttling de los pods de la API.
- Al terminar, el dashboard completo con los 4 escalones.

### Al terminar

```bash
column -s, -t < locust/resultados/resumen.csv     # filas de las dos pruebas; replicas = pods vistos en el escalón
kubectl -n housing-mlops get hpa api
kubectl -n housing-mlops top pod -l app=api
kubectl -n housing-mlops get pods -l app=api      # RESTARTS
kubectl -n housing-mlops describe hpa api | tail -12    # eventos de escalado
```

## 3. Qué enviar a Cristhian

1. La salida y las capturas de la sección 1.
2. La salida de "Al terminar" (sección 2).
3. Las capturas de la terminal 2 y de Grafana.

Con eso se completa el análisis de carga del README:
- 2 réplicas fijas frente a HPA de 2 a 3;
- cuánto crece el throughput;
- si la latencia baja;
- qué limita (CPU del nodo, Prometheus y Grafana en el mismo nodo).
