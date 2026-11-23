# PR 10a: imagen de Airflow en CI (Cristian Organista)

**Depende del PR 9 (ya fusionado).** Este PR solo publica la imagen y deja los valores del chart: todavía no despliega nada. El 10b se abre después de que el bot de GitHub Actions cambie el tag en `airflow/values.yaml`.

**¿Por qué va separado del 10b?** Si Argo sincroniza Airflow antes de que la imagen exista en DockerHub, el Job de migraciones queda en `ImagePullBackOff`. Argo se queda esperando ese hook y la sincronización no avanza. A diferencia de MLflow en el PR 8, esto no se arregla solo.

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/imagen-airflow

# copiar el contenido de este directorio sobre la raíz del repo:
# .github/workflows/build-airflow.yml y airflow/values.yaml (los dos son nuevos)

git add airflow/values.yaml
git commit -m "Valores del chart de Airflow"
git add .github/workflows/build-airflow.yml
git commit -m "Build de la imagen de Airflow en GitHub Actions"
git push -u origin feature/imagen-airflow
```

**Título del PR:** `Imagen de Airflow publicada por CI y valores del chart`

**Qué cambia**

- `.github/workflows/build-airflow.yml`:
  - usa el workflow reutilizable `_build-push.yml`, igual que MLflow;
  - el contexto es la raíz del repo, porque la imagen instala `housing_ml`;
  - en un push a `master` construye `linux/amd64`, publica `crissebasbol/housing-airflow:sha-<7>` y cambia `images.airflow.tag` en `airflow/values.yaml` con un commit `[skip ci]`;
  - en un PR solo construye, sin publicar;
  - se dispara con cambios en el Dockerfile, `requirements.txt`, `airflow/dags/` y `housing_ml/`.
- `airflow/values.yaml`: valores del chart oficial 1.22.0, que usa Argo en el PR 10b:
  - LocalExecutor, Airflow 3.1.8 e imagen propia, todo en el nodo de datos;
  - configuración del pipeline desde el ConfigMap `airflow-pipeline`; credenciales desde Secrets (`DATA_DB_PASSWORD` de `postgres-data` y `AWS_*` de `minio-airflow`);
  - conexión a metadatos, clave Fernet, clave de la API y secreto JWT desde Secrets estables;
  - sin Redis, StatsD, PgBouncer ni el PostgreSQL del chart;
  - recursos por componente: el scheduler pide 2 Gi y tiene límite de 4 Gi, porque con LocalExecutor el entrenamiento corre ahí (pico medido de 1,0 GiB con 757 mil filas); `OMP_NUM_THREADS=2` igual al límite de CPU;
  - los Jobs de migraciones y de usuario son hooks `Sync` de Argo;
  - la contraseña del admin sale del Secret `airflow-admin`.

**Por qué**

La imagen queda versionada por commit y el tag se actualiza solo en Git (GitOps). Las claves salen de Secrets, no del chart. Si el chart las generara, Argo vería claves aleatorias nuevas en cada renderizado: la app quedaría siempre *OutOfSync* y los pods se reiniciarían.

**Cómo se probó**

- [x] `helm template` del chart 1.22.0 con estos valores y `kubeconform`: 21 recursos válidos
- [x] Memoria del entrenamiento medida con la imagen local y los datos de la prueba de punta a punta: pico de 1,0 GiB
- [ ] CI del PR: `Build Airflow` construye la imagen (completar)

## Después de fusionar

| Qué | Dónde | Esperado |
|---|---|---|
| Workflow | GitHub, pestaña Actions, `Build Airflow` en `master` | Jobs `build` y `update-manifest` en verde |
| Imagen | DockerHub, `crissebasbol/housing-airflow` | Tag `sha-<7>` del merge |
| Commit del bot | Historial de `master` | `Imagen airflow sha-<7> [skip ci]`, que cambia `bootstrap` por el tag en `airflow/values.yaml` |

**Capturas para el README:** la corrida de Actions, el tag en DockerHub y el diff del commit del bot.

## Para explicarlo

- **¿Por qué el contexto de build es la raíz?** La imagen instala `housing_ml`, el mismo paquete que usará la API. Así las dos tienen las mismas versiones de scikit-learn y numpy.
- **¿Por qué los Jobs son hooks de Argo?** Un Job no se puede modificar después de creado. Cuando cambia el tag de la imagen, Argo no podría actualizarlo. Como hook `Sync` con `BeforeHookCreation`, Argo lo borra y lo crea de nuevo en cada sincronización, así las migraciones corren con cada versión nueva de la imagen.
- **¿Cómo llega la contraseña del admin sin estar en Git?** El valor es `$(AIRFLOW_ADMIN_PASSWORD)`. Kubernetes reemplaza `$(VAR)` en los argumentos del contenedor con la variable de entorno, y esa variable sale del Secret `airflow-admin`.
