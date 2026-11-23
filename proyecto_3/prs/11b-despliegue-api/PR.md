# PR 11b: despliegue de la API con Argo CD (Fabián Ramírez)

**Depende del 11a fusionado y del commit del bot.** Antes de empezar, en `master` la imagen de `api/k8s/deployment.yaml` debe ser `crissebasbol/housing-api:sha-...` y no `bootstrap`.

## Pasos (git)

```bash
cd housing-price-mlops
git switch master && git pull
grep "image:" api/k8s/deployment.yaml      # debe decir sha-..., no bootstrap
git switch -c feature/despliegue-api

# copiar el contenido de este directorio sobre la raíz del repo:
# serving/ y argocd/apps/serving.yaml (nuevos); argocd/apps/kustomization.yaml,
# argocd/README.md, scripts/create_secrets.sh y .env.example (reemplazan)

git add scripts/create_secrets.sh .env.example
git commit -m "Secret api-admin para la API"
git add serving argocd/apps/serving.yaml argocd/apps/kustomization.yaml argocd/README.md
git commit -m "App serving de Argo CD con la API"
git push -u origin feature/despliegue-api
```

## Antes de fusionar: Secret `api-admin` (en la .106)

`API_ADMIN_TOKEN` ya está en el `.env` de la .106 desde el principio. Solo falta crear el Secret desde la rama:

```bash
cd ~/housing-price-mlops
git fetch && git switch feature/despliegue-api
./scripts/create_secrets.sh               # vuelve a aplicar los anteriores y crea api-admin
kubectl -n housing-mlops get secrets      # 13 en total
git switch master
```

**Título del PR:** `Despliegue de la API de inferencia con Argo CD`

**Qué cambia**

- `serving/kustomization.yaml`: agrupa lo que corre en el nodo de serving, en el namespace `housing-mlops`. Por ahora es la API; Streamlit se agrega aquí.
- `argocd/apps/serving.yaml`: app `serving` (ola 2, después de `data-platform` y `airflow`) con `automated`, `prune`, `selfHeal` y reintentos.
- `argocd/apps/kustomization.yaml` y `argocd/README.md`: la app nueva.
- `scripts/create_secrets.sh`: Secret `api-admin` (clave `token`) con `API_ADMIN_TOKEN`.
- `.env.example`: agrega `AIRFLOW_JWT_SECRET` y `AIRFLOW_FERNET_KEY`, que `create_secrets.sh` ya exige desde el #16 pero no quedaron en el ejemplo.

**Por qué**

La API se despliega igual que el resto: desde Git, con Argo CD, sin `kubectl apply` a mano. Va en una app aparte de la plataforma de datos porque corre en otro nodo y tiene otro ciclo de cambios.

**Cómo se probó**

- [x] `kubectl kustomize` y `kubeconform` de `serving` (3 recursos) y `argocd/apps` (3 apps)
- [x] `shellcheck` de `create_secrets.sh`
- [ ] Sincronización en el clúster (completar con lo que pasó)

## Después de fusionar (en la .106)

```bash
cd ~/housing-price-mlops && git switch master && git pull
argocd app get serving --refresh
kubectl -n housing-mlops get pods -l app=api -o wide -w     # Ctrl+C cuando estén Running
kubectl -n housing-mlops logs deploy/api | grep -E "Champion|ERROR" | tail
curl -s http://10.43.97.106:8005/health
curl -s http://10.43.97.106:8005/model-info
```

El port-forward de 8005 ya existe y se reconecta solo cuando aparece el Service. Si `port_forward.sh status` dice FALLA en 8005, corre `./scripts/port_forward.sh start`.

**Si en el clúster todavía no hay champion** (el lote 0 fue rechazado por G6), `/health` dice `model_loaded: false` y `/predict` responde 503. Es lo esperado: en cuanto Airflow promueva el primer modelo, las dos réplicas lo cargan solas en 30 s o menos, sin reiniciar. Cada una deja una fila `reload` en `audit.model_actions` con su nombre de pod. Esa es la evidencia de la recarga en caliente.

Verificar:

| Qué | Cómo | Esperado |
|---|---|---|
| App | UI de Argo (`https://10.43.97.106:8006`) | `serving` en *Synced* y *Healthy* |
| Pods | `kubectl -n housing-mlops get pods -l app=api -o wide` | 2 réplicas `api-...` en `nodo-serving`, `Running` |
| Imagen | `kubectl -n housing-mlops get deploy api -o jsonpath='{.spec.template.spec.containers[0].image}'` | `crissebasbol/housing-api:sha-...`, el del commit del bot |
| Swagger | `http://10.43.97.106:8005/docs` | Endpoints de inferencia, modelo, administración y operación |
| Predicción | `POST /predict` desde Swagger con el ejemplo | 200 con `model_version` y `model_alias=champion` (o 503 si aún no hay champion) |
| Métricas | `http://10.43.97.106:8005/metrics` | `predictions_total`, `model_info`, `http_request_duration_seconds` |
| Registro | `kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "SELECT traffic_source, status, count(*) FROM raw.inference_events GROUP BY 1, 2"` | Una fila por cada predicción hecha |
| Recargas | `kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "SELECT ts, action, from_version, to_version, actor FROM audit.model_actions ORDER BY id"` | Un `reload` por réplica cada vez que cambia el champion |

El rollback (`POST /admin/rollback` con el token) solo se puede probar cuando exista `previous_champion`, es decir, después de la segunda promoción.

**Capturas para el README:**
- la app `serving` en Argo;
- los pods en `nodo-serving`;
- Swagger, y una predicción con su respuesta;
- `/model-info` y `/explain`;
- `audit.model_actions` con los `reload` de las dos réplicas;
- un extracto de `/metrics`.

## Para explicarlo

- **¿Por qué una app `serving` aparte?** Agrupa lo que corre en el nodo de inferencia (API y luego Streamlit). Se sincroniza y se revierte por separado de la plataforma de datos.
- **¿Por qué el token no está en Git?** Sale del Secret `api-admin`, creado desde el `.env` local con `create_secrets.sh`, igual que las contraseñas.
- **¿Qué pasa si se cae una réplica?** El Service manda el tráfico a la otra. La nueva réplica arranca, lee el alias y carga el mismo champion; no hay versión fija en la imagen.
