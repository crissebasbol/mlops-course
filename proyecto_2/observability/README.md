# observability

## Prometheus

- `prometheus/prometheus.yml` (ConfigMap `prometheus-config`), scrape cada 5 s.
- Job `api`: descubre los pods del namespace con la anotación `prometheus.io/scrape: "true"`
  y raspa **cada réplica** por separado (labels `pod` y `node`).
- Job `kubelet-cadvisor`: CPU, memoria y throttling por contenedor desde el kubelet de cada
  nodo (solo del namespace `proyecto2`).
- `k8s/rbac.yaml`: ServiceAccount con permisos de lectura de pods, nodos y métricas del kubelet.

## Grafana

- Datasource y proveedor de dashboards provisionados por ConfigMap
- Dashboard `dashboards/proyecto2-api.json` (carpeta MLOps, también es el home).