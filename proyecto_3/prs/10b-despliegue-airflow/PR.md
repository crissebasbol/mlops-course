# PR 10b: despliegue de Airflow con Argo CD (Cristian Organista)

**Depende del 10a fusionado y del commit del bot.** Antes de empezar, `airflow/values.yaml` en `master` debe tener un tag `sha-...` y no `bootstrap`.

## Pasos (git)

```bash
cd housing-price-mlops
git switch master && git pull
grep "tag:" airflow/values.yaml          # debe decir sha-..., no bootstrap
git switch -c feature/despliegue-airflow

# copiar el contenido de este directorio sobre la raíz del repo:
# airflow/k8s/ (nuevo), argocd/apps/airflow.yaml (nuevo), y reemplazar
# argocd/apps/kustomization.yaml, argocd/README.md, scripts/create_secrets.sh,
# scripts/port_forward.sh, .env.example y .github/workflows/ci.yml

git add airflow/k8s
git commit -m "PostgreSQL de metadatos y ConfigMap del pipeline"
git add scripts/create_secrets.sh .env.example
git commit -m "Secrets de Airflow"
git add argocd/apps/airflow.yaml argocd/apps/kustomization.yaml argocd/README.md
git commit -m "App de Argo CD para Airflow"
git add .github/workflows/ci.yml
git commit -m "CI valida los valores del chart de Airflow"
git add scripts/port_forward.sh
git commit -m "port_forward.sh muestra el estado al iniciar"
git push -u origin feature/despliegue-airflow
```

## Antes de fusionar: Secrets (en la .106)

Argo necesita los Secrets antes de sincronizar. Pasos:

1. **Actualizar el `.env` de la .106.** Cristhian te pasa dos líneas nuevas: `AIRFLOW_JWT_SECRET` y `AIRFLOW_FERNET_KEY`. Agrégalas al `.env` de la .106; las demás ya están.
2. **Crear los Secrets desde la rama**, antes de fusionar:

```bash
cd ~/housing-price-mlops
git fetch && git switch feature/despliegue-airflow
./scripts/create_secrets.sh              # vuelve a aplicar los 6 anteriores y crea los 6 de Airflow
kubectl -n housing-mlops get secrets     # 12 en total
git switch master
```

Secrets nuevos: `postgres-airflow`, `airflow-metadata`, `airflow-fernet-key`, `airflow-api-secret-key`, `airflow-jwt-secret` y `airflow-admin`.

**La clave Fernet no se cambia nunca.** Airflow cifra con ella las conexiones y variables guardadas; si cambia, no puede leerlas.

**Título del PR:** `Despliegue de Airflow con Argo CD`

**Qué cambia**

- `airflow/k8s/postgres-airflow.yaml`: PostgreSQL 16 para los metadatos de Airflow (StatefulSet y Service, PVC de 2 Gi, nodo de datos, probes y recursos). Va en la ola -1 para existir antes de las migraciones.
- `airflow/k8s/configmap.yaml`: ConfigMap `airflow-pipeline` con la configuración del pipeline, sin secretos:
  - frecuencia de cada 15 min;
  - grupo 1 y día martes de la API de datos;
  - política de reinicio al terminar los datos;
  - direcciones de PostgreSQL, MinIO y MLflow;
  - experimento y modelo.
- `argocd/apps/airflow.yaml`: app multi-source con tres fuentes: el chart oficial 1.22.0 desde `airflow.apache.org`, los valores desde este repo (`$values/airflow/values.yaml`) y `airflow/k8s/`. Usa `automated`, `prune`, `selfHeal` y reintentos. Va en la ola 1, después de `data-platform`.
- `scripts/create_secrets.sh` y `.env.example`: los 6 Secrets de Airflow, con dos claves nuevas, `AIRFLOW_JWT_SECRET` y `AIRFLOW_FERNET_KEY`.
- `.github/workflows/ci.yml`: el job `manifests` renderiza el chart con `airflow/values.yaml` (la versión la lee de la app de Argo) y lo valida con `kubeconform`. Un `values.yaml` roto falla en el PR y no en Argo.
- `scripts/port_forward.sh`: `start` espera 5 s y muestra el estado. Antes salía FALLA porque los port-forward todavía no estaban arriba.
- `argocd/README.md`: fila de la app `airflow`.

**Por qué**

Airflow es el orquestador del pipeline (sección 5 del enunciado) y Argo CD es el mecanismo de despliegue: Airflow sale de Git como el resto de la plataforma, sin `helm install` a mano.

**Cómo se probó**

- [x] `kubectl kustomize` y `kubeconform` de `airflow/k8s` (3 recursos) y `argocd/apps` (2 apps)
- [x] `helm template` del chart con `values.yaml` y `kubeconform`: 21 recursos válidos
- [x] `shellcheck` de los dos scripts
- [ ] Sincronización en el clúster (completar con lo que pasó)

## Después de fusionar (en la .106)

```bash
cd ~/housing-price-mlops && git switch master && git pull
argocd app get airflow                     # si no aparece en 3 min: Refresh en housing-root
kubectl -n housing-mlops get pods -o wide -w   # Ctrl+C cuando todo esté Running
kubectl -n housing-mlops get jobs          # los Jobs se borran solos a los 5 min
kubectl -n housing-mlops logs job/airflow-run-airflow-migrations | tail -5
./scripts/port_forward.sh start
```

Verificar:

| Qué | Cómo | Esperado |
|---|---|---|
| App | UI de Argo (`https://10.43.97.106:8006`) | `airflow` en *Synced* y *Healthy* |
| Pods | `kubectl -n housing-mlops get pods -o wide` | `postgres-airflow-0`, `airflow-scheduler-0`, `airflow-api-server`, `airflow-dag-processor` y `airflow-triggerer` en `nodo-data`, todos `Running` |
| Imagen | `kubectl -n housing-mlops get pod airflow-scheduler-0 -o jsonpath='{.spec.containers[0].image}'` | `crissebasbol/housing-airflow:sha-...`, el del commit del bot |
| UI | `http://10.43.97.106:8002`, usuario `admin` y la contraseña `AIRFLOW_ADMIN_PASSWORD` del `.env` | DAG `housing_pipeline` sin errores de importación y **pausado** |

## Primera corrida en el clúster: solo el lote 0

Corre el DAG una sola vez para verificar todo de punta a punta, y **déjalo pausado**. Los demás lotes se corren cuando la API esté desplegada (PR 11): así cada promoción se ve llegar a la API en vivo. Después del primer ciclo todos los lotes son repetidos y ya no hay más entrenamientos.

```bash
# la API de datos empieza desde el lote 0 (no importa si nadie la ha usado)
curl "http://10.43.97.106:8011/restart_data_generation?group_number=1&day=Tuesday"

# una corrida completa del DAG dentro del scheduler (funciona con el DAG pausado)
kubectl -n housing-mlops exec airflow-scheduler-0 -c scheduler -- airflow dags test housing_pipeline
```

En la prueba local tardó 1 min; en el clúster puede tardar unos 3. Esperado:

| Qué | Dónde | Esperado |
|---|---|---|
| Corrida | UI de Airflow, Grid de `housing_pipeline` | Corrida en verde: `route_batch` va a `validate_schema`, `decide_training` a `train_candidate_model` y `decide_promotion` a `promote_model` |
| Modelo | MLflow (`:8003`), Models, `housing-price-model` | Versión 1 con alias `champion` |
| Run | MLflow, experimento `housing-price` | Run `c1-b0-...` con tags (`git_sha` igual al de la imagen), métricas, gráficos, SHAP y `promotion/gates.json` |
| Landing | MinIO (`:8004`), bucket `landing` | `cycle=1/batch=0/...json.gz` |
| Auditoría | `kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "SELECT ingestion_id, api_batch_number, outcome, final_status, training_code, promotion_decision FROM audit.batch_runs"` | `1 \| 0 \| new \| success \| baseline \| promoted` |

**Capturas para el README:** la app `airflow` en Argo, los pods, el Graph de la corrida con las ramas tomadas, la versión 1 *champion* en MLflow, los artefactos del run (gráficos y SHAP), el landing en MinIO y la fila de auditoría.

## Para explicarlo

- **¿Qué es una app multi-source?** Una app de Argo con varias fuentes: el chart viene del repositorio oficial de Helm y los valores vienen de nuestro Git. Cambiar `values.yaml` en `master` redespliega Airflow.
- **¿Por qué un PostgreSQL aparte para Airflow?** Los metadatos de Airflow (corridas, estados, usuarios) no se mezclan con los datos del proyecto (RAW, CLEAN y auditoría), y cada base tiene su propio volumen.
- **¿Por qué LocalExecutor?** Las tareas corren como procesos dentro del scheduler. Con un DAG de una corrida a la vez (`max_active_runs=1`) no hace falta Celery, Redis ni workers aparte.
- **¿Por qué `airflow dags test` para la primera corrida?** Ejecuta el DAG completo una vez aunque esté pausado, y queda registrado en la UI. Con el DAG pausado el horario de cada 15 min no arranca hasta que lo decidamos.
