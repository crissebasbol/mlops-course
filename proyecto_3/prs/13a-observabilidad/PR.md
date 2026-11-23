# PR 13a: Prometheus y Grafana (Fabián Ramírez)

**Depende del 11b (fusionado).** Todo usa imágenes oficiales con versión fija (`prom/prometheus:v3.5.0`, `grafana/grafana:12.1.0`), así que no hay imagen propia ni workflow de build: la app de Argo va en este mismo PR. Locust va aparte en el 13b para desplegar primero Prometheus y Grafana, comprobar los targets y después generar carga.

Validado en local:

- `kubectl kustomize observability` y `kubeconform`: 13 recursos válidos.
- `promtool check config`: configuración válida.
- Prueba en Docker con la API real (champion v5, sombra v4) y 90 s de Locust:
  - 24 de las 34 consultas PromQL del dashboard devolvieron datos.
  - Las vacías son las de errores (hubo 0 fallos) y las de cAdvisor (solo existen en el clúster).
  - Grafana: las dos fuentes de datos en OK, el dashboard en la carpeta "Housing MLOps" y el panel de replay con MAPE del champion de 24,4 % y de la sombra de 29,9 %.

## Pasos (git)

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/observabilidad

# copiar observability/ (nuevo) y argocd/apps/observability.yaml (nuevo).
# NO reemplazar argocd/apps/kustomization.yaml, argocd/README.md ni scripts/create_secrets.sh
# (el PR 12 de Streamlit puede haberlos cambiado): agregar a mano lo que está en "Cambios a mano".

git add observability/prometheus
git commit -m "Prometheus con la API, la API de datos y cAdvisor"
git add observability/grafana observability/kustomization.yaml observability/README.md
git commit -m "Grafana con el dashboard Housing API"
git add scripts/create_secrets.sh
git commit -m "Secret de Grafana"
git add argocd/apps/observability.yaml argocd/apps/kustomization.yaml argocd/README.md
git commit -m "App de Argo CD para la observabilidad"
git push -u origin feature/observabilidad
```

### Cambios a mano

`argocd/apps/kustomization.yaml`, al final de `resources`:

```yaml
  - observability.yaml
```

`scripts/create_secrets.sh`, al final:

```bash

require GRAFANA_ADMIN_PASSWORD
apply_secret grafana-admin --from-literal=password="$GRAFANA_ADMIN_PASSWORD"
```

`argocd/README.md`, debajo de la fila de `apps/serving.yaml`:

```markdown
| `apps/observability.yaml` | `observability` | `observability/`: Prometheus y Grafana con el dashboard "Housing API" en el nodo de serving |
```

y el párrafo de abajo queda así:

```markdown
Streamlit se agrega a `serving/` y Locust a `observability/`. Una app nueva es un archivo más en `apps/` (y en `apps/kustomization.yaml`); la app raíz la crea sola en la siguiente sincronización.
```

## Antes de fusionar: Secret de Grafana (en la .106)

`GRAFANA_ADMIN_PASSWORD` ya está en el `.env` de la .106.

```bash
cd ~/housing-price-mlops
git fetch && git switch feature/observabilidad
./scripts/create_secrets.sh
kubectl -n housing-mlops get secret grafana-admin     # debe existir (14 Secrets en total)
git switch master
```

**Título del PR:** `Observabilidad: Prometheus y Grafana`

**Qué cambia**

- `observability/prometheus/prometheus.yml` recolecta cuatro fuentes:
  - las réplicas de la API, encontradas con `kubernetes_sd` por la anotación `prometheus.io/scrape`, cada 5 s;
  - la API de datos;
  - el cAdvisor de cada kubelet (CPU, memoria, límites y throttling del namespace);
  - Prometheus mismo.
- `observability/prometheus/k8s/`:
  - ServiceAccount y ClusterRole de solo lectura (pods, servicios, endpoints, nodos y `nodes/metrics`);
  - Deployment con PVC de 5 Gi, retención de 7 días o 4 GB, probes, recursos y nodo de serving;
  - Service.
- `observability/grafana/provisioning/`:
  - fuente Prometheus;
  - fuente PostgreSQL con el rol `app_reader`, cuya contraseña sale del Secret `postgres-data`;
  - proveedor de dashboards de solo lectura.
- `observability/grafana/k8s/dashboard-configmap.yaml`: dashboard **Housing API** con el JSON embebido en un ConfigMap; 26 paneles en 6 filas:
  - resumen;
  - tráfico y latencia (p50/p95/p99 y por rol champion/sombra);
  - modelo (versión cargada por réplica, recargas, sombra vs champion, categorías no vistas);
  - registro de inferencias;
  - recursos por cAdvisor;
  - replay (MAPE en línea desde `audit.replay_accuracy`) y API de datos.
- `observability/grafana/k8s/`: Deployment con PVC de 1 Gi, admin desde el Secret `grafana-admin` y el dashboard como página de inicio; y su Service.
- `observability/kustomization.yaml`: los ConfigMaps de configuración llevan hash en el nombre, así que un cambio de configuración reinicia el pod solo. El dashboard se actualiza sin reiniciar.
- `argocd/apps/observability.yaml`: app `observability`, ola 3, `automated`, `prune` y `selfHeal`.
- `scripts/create_secrets.sh`: Secret `grafana-admin`.

**Por qué**

RF10 y la sección de observabilidad del enunciado:
- métricas de la API (peticiones, latencia, errores, versión del modelo) y de los recursos del contenedor;
- dashboard versionado en Git;
- todo desplegado en Kubernetes por Argo CD.

El panel de replay mide el error real del modelo en producción con filas holdout de precio conocido.

**Cómo se probó**

- [x] `kubectl kustomize` y `kubeconform` (13 recursos) y `promtool check config`
- [x] Prueba en Docker con la API real, Prometheus, Grafana y Locust: datos en 24 de 34 consultas (las vacías: errores en cero y cAdvisor), fuentes de datos OK, MAPE del replay visible
- [ ] Probado en el clúster: targets arriba y dashboard con datos (completar)

**Checklist**

- [x] Sin secretos en el diff (la contraseña de Grafana y la de `app_reader` llegan desde Secrets)
- [x] Contenedores nuevos con `requests`, `limits` y probes

## Después de fusionar (en la .106)

```bash
cd ~/housing-price-mlops && git switch master && git pull
argocd app get housing-root --refresh | tail -3
argocd app get observability | tail -15
kubectl -n housing-mlops get pods -o wide | grep -E "prometheus|grafana"
kubectl -n housing-mlops get pvc | grep -E "prometheus|grafana"
./scripts/port_forward.sh start
```

| Qué | Dónde | Esperado |
|---|---|---|
| App | UI de Argo (`:8006`) | `observability` en *Synced/Healthy* |
| Pods | `kubectl get pods -o wide` | `prometheus` y `grafana` `Running` en `nodo-serving` |
| Targets | Prometheus `http://10.43.97.106:8009/targets` | `api` con 2 targets (uno por réplica), `data-api`, `kubelet-cadvisor` con 2 nodos y `prometheus`, todos *UP* |
| Dashboard | Grafana `http://10.43.97.106:8008` (admin y `GRAFANA_ADMIN_PASSWORD`) | Housing API como inicio, versión champion visible, paneles de CPU y memoria por pod con datos |
| Fuentes | Grafana, Connections, Data sources | Prometheus y Housing Postgres con *Save & test* en verde |

Si `kubelet-cadvisor` aparece *DOWN* con 403, falta el permiso `nodes/metrics`. Revisar con `kubectl auth can-i get nodes/metrics --as=system:serviceaccount:housing-mlops:prometheus`.

**Capturas para el README:**
- la app en Argo;
- la página de targets de Prometheus (evidencia 17);
- el dashboard Housing API con la versión champion y el tráfico normal, antes de la prueba de carga (sirve para comparar después).

## Para explicarlo

- **¿Cómo encuentra Prometheus las réplicas?** Con `kubernetes_sd` pregunta al API de Kubernetes por los pods anotados con `prometheus.io/scrape`. Si la API pasa de 2 a 3 réplicas, el target nuevo aparece solo.
- **¿De dónde salen CPU y memoria?** Del cAdvisor que trae cada kubelet. Prometheus entra con el token de su ServiceAccount y el RBAC le permite solo leer `nodes/metrics`.
- **¿Por qué el dashboard en un ConfigMap?** Queda versionado en Git y lo despliega Argo como cualquier otro recurso. Si alguien lo cambia en la UI, Grafana no lo guarda: el dashboard verdadero es el de Git.
- **¿Qué es el MAPE en línea del replay?** Locust manda filas holdout con su `row_hash`. La vista `audit.replay_accuracy` une cada predicción con su precio real y calcula el error del champion y de la sombra minuto a minuto.
