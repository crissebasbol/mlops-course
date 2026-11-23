# Observabilidad

Prometheus y Grafana corren en el nodo de serving y los despliega la app `observability` de Argo CD. Locust (`locust/`) se agrega a esta misma app.

## Prometheus (`prometheus/`)

`prom/prometheus:v3.5.0`, 7 días o 4 GB de retención en un PVC de 5 Gi. Qué recolecta (`prometheus.yml`):

| Job | Cómo encuentra el objetivo | Qué trae |
|---|---|---|
| `api` | `kubernetes_sd` de pods con la anotación `prometheus.io/scrape: "true"`, cada 5 s | Cada réplica de la API por separado: peticiones, latencia, modelo cargado, sombra, registro de inferencias |
| `data-api` | Service `data-api:80` | Peticiones a `/data`, lote actual y registros servidos |
| `kubelet-cadvisor` | `kubernetes_sd` de nodos, `/metrics/cadvisor` del kubelet con el token de la ServiceAccount | CPU, memoria, límites y throttling por contenedor del namespace `housing-mlops` |
| `prometheus` | estático | Prometheus mismo |

El RBAC (`k8s/rbac.yaml`) da a la ServiceAccount `prometheus` solo lectura de pods, servicios, endpoints, nodos y `nodes/metrics`.

## Grafana (`grafana/`)

`grafana/grafana:12.1.0`. Fuentes de datos aprovisionadas:

- **Prometheus** (por defecto).
- **Housing Postgres**: la base de datos con el rol `app_reader` (solo lectura); la contraseña llega del Secret `postgres-data`.

El dashboard **Housing API** está en `k8s/dashboard-configmap.yaml`, un ConfigMap con el JSON embebido. Es la página de inicio de Grafana.

| Fila | Paneles |
|---|---|
| Resumen | Peticiones por segundo, latencia p95 de `/predict`, tasa de error 5xx, versión champion, réplicas arriba, lote actual de la API de datos |
| Tráfico y latencia | Peticiones por endpoint y código, por réplica, latencia p50/p95/p99 de `/predict`, latencia del modelo por rol (champion y sombra), errores, peticiones en curso |
| Modelo | Versión cargada por réplica (el cambio de serie es la recarga en caliente), predicciones por rol, recargas y fallos, diferencia sombra vs champion, categorías no vistas |
| Registro de inferencias | Tiempo de escritura en Postgres, cola y eventos perdidos |
| Recursos (cAdvisor) | CPU y memoria por pod con su límite, CPU throttling |
| Replay y API de datos | MAPE en línea del replay (vista `audit.replay_accuracy`), peticiones de replay, peticiones a la API de datos, targets de Prometheus |

El aprovisionamiento no guarda cambios hechos en la UI (`allowUiUpdates: false`). Para cambiar el dashboard: editarlo en Grafana, exportar el JSON y reemplazar el bloque `housing-api.json` del ConfigMap. Grafana relee la carpeta cada 30 s.

## Acceso

```bash
./scripts/port_forward.sh start
```

- Grafana: `http://10.43.97.106:8008` (usuario `admin`, contraseña `GRAFANA_ADMIN_PASSWORD` del `.env`).
- Prometheus: `http://10.43.97.106:8009` (Status, Targets).
