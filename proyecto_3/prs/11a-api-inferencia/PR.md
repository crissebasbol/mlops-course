# PR 11a: API de inferencia (Fabián Ramírez)

**Depende del 10b (ya fusionado).** Este PR trae el código, las pruebas, la imagen y los manifiestos de la API, pero **no la agrega a Argo CD**. El 11b la despliega después de que el bot de GitHub Actions cambie el tag `bootstrap` por el de la imagen publicada (la misma lección del 10a y el 10b).

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/api-inferencia

# copiar el contenido de este directorio sobre la raíz del repo:
# api/ y .github/workflows/build-api.yml (nuevos); pyproject.toml, ruff.toml y uv.lock (reemplazan)

uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest

git add pyproject.toml ruff.toml uv.lock api/housing_api api/tests api/requirements.txt api/README.md
git commit -m "API de inferencia con recarga del champion y sombra"
git add api/Dockerfile .github/workflows/build-api.yml
git commit -m "Imagen de la API publicada por CI"
git add api/kustomization.yaml api/k8s
git commit -m "Manifiestos de la API"
git push -u origin feature/api-inferencia
```

Si antes de este PR se fusionó otro que cambie `pyproject.toml` o `uv.lock`, no los reemplaces. En ese caso agrega a mano los tres paquetes del grupo `dev` (`fastapi==0.162.2`, `httpx==0.28.1`, `prometheus-client==0.26.0`), `api/tests` en `testpaths` y `api` en `pythonpath`, y corre `uv lock`.

**Título del PR:** `API de inferencia: champion de MLflow, sombra, rollback, SHAP y métricas`

**Qué cambia**

- `api/housing_api/`: FastAPI con un módulo por responsabilidad.
  - `registry.py`: resuelve los alias de `housing-price-model` en MLflow y carga el modelo con skops, igual que Airflow (tipos confiables del MLmodel y descarga por el proxy de artefactos, con `MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false`).
  - `models.py`: champion y sombra.
    - Un hilo revisa los alias cada 30 s y solo descarga cuando cambia la versión.
    - Carga fuera del lock y cambia los dos modelos en un solo paso.
    - Si la descarga falla, sigue con el modelo anterior.
    - Al promover, reutiliza el challenger ya cargado.
  - `main.py`: los endpoints.
    - `/predict`, `/explain` y `/feedback`.
    - `/model-info`, `/health` y `/metrics`.
    - `/admin/reload` y `/admin/rollback`, protegidos con Bearer `API_ADMIN_TOKEN`.
    - Sin champion, `/predict` responde 503 y `/health` sigue en 200.
  - `inference_log.py`: cola en memoria y escritura por lotes en `raw.inference_events` con el rol `api_writer`. También guarda el feedback y las acciones en `audit.model_actions`, incluida cada recarga automática con el nombre del pod.
  - `explain.py`: SHAP (`TreeExplainer`) en escala log del precio, convertido a efecto % sobre el precio. Se prepara al cargar cada champion.
  - `schemas.py`: validación con Pydantic usando los mismos rangos de `housing_ml.cleaning.RANGES` que el pipeline.
  - `metrics.py`: las métricas de Prometheus de la sección 13 del plan.
- `api/tests/`: 16 pruebas con registro y base de datos falsos y modelos reales de `housing_ml` entrenados con pocos datos.
- `api/Dockerfile`:
  - `python:3.12-slim` con `housing_ml` y las mismas versiones de scikit-learn y numpy que Airflow;
  - un hilo (`OMP_NUM_THREADS=1`), usuario sin privilegios y `uvicorn` con un worker;
  - el build falla si la app no importa.
- `.github/workflows/build-api.yml`: usa `_build-push.yml` con contexto raíz. En `master` publica `crissebasbol/housing-api:sha-<7>` y actualiza la imagen en `api/k8s/deployment.yaml`.
- `api/k8s/`:
  - Deployment de 2 réplicas en el nodo de serving, con requests, limits, probes en `/health` y anotaciones de Prometheus;
  - Service `api:8000` y ConfigMap `api`;
  - la contraseña de `api_writer` sale del Secret `postgres-data` y el token del Secret `api-admin` (lo crea el 11b).
- `pyproject.toml`, `ruff.toml` y `uv.lock`: pruebas y lint de `api/`.

**Por qué**

Requisitos de inferencia del enunciado. La API usa siempre el modelo productivo del registro, sin versiones fijas, y toma cada promoción sin redespliegue. La sombra y el replay comparan champion y challenger con tráfico real. Las inferencias que llegan desde la API y Streamlit alimentan la señal de drift del DAG (`INFERENCE_SOURCES_FOR_DRIFT`). Detalle en la sección 13 del plan.

**Cómo se probó**

- [x] `ruff check`, `ruff format --check` y `pytest`: 79 pruebas, 16 de ellas nuevas.
- [x] Imagen construida en local: 902 MB, scikit-learn 1.8.0 y numpy 2.4.2, iguales a la imagen de Airflow.
- [x] API contra la prueba de punta a punta en Docker (MLflow con las versiones 1 a 5 y Postgres real):
  - carga el champion v5 en unos 6 s;
  - 200 predicciones: p50 de 29 ms y p95 de 36 ms con 1 CPU, incluido HTTP;
  - `/explain` en 35 ms; SHAP reconstruye la predicción exacta (280.102);
  - sombra v4 guardada en el mismo evento que el champion (unos 20 ms);
  - rollback 5 → 4 y vuelta a 5, y recarga forzada, todo en `audit.model_actions`;
  - respuestas 422 y 503 registradas, feedback guardado;
  - memoria de 316 MiB.
- [x] Hallazgo de esa prueba: `INSERT ... ON CONFLICT` exige `SELECT` y el rol `api_writer` solo tiene `INSERT`. Se quitó (el `request_id` es un UUID nuevo en cada petición). Mientras falló, las predicciones siguieron funcionando y se contaron los errores, como está diseñado.
- [x] `kubectl kustomize api` y `kubeconform`: 3 recursos válidos.
- [ ] CI del PR: `Build API` construye la imagen (completar).

**Checklist**

- [x] Sin secretos en el diff (contraseña y token salen de Secrets)
- [x] Mismas versiones de scikit-learn y numpy en Airflow y en la API (fijadas en `housing_ml`)
- [x] Contenedores con `requests`, `limits` y probes

## Después de fusionar

| Qué | Dónde | Esperado |
|---|---|---|
| Workflow | GitHub, pestaña Actions, `Build API` en `master` | `build` y `update-manifest` en verde |
| Imagen | DockerHub, `crissebasbol/housing-api` | Tag `sha-<7>` del merge |
| Commit del bot | Historial de `master` | `Imagen api sha-<7> [skip ci]`, que cambia `housing-api:bootstrap` en `api/k8s/deployment.yaml` |

**Capturas para el README:** la corrida de `Build API`, el tag en DockerHub y el diff del commit del bot.

## Para explicarlo

- **¿Cómo cambia de modelo sin reiniciar?** Un hilo pregunta a MLflow cada 30 s a qué versión apunta `champion`. Si cambió, descarga la nueva en paralelo mientras la anterior sigue respondiendo, y las intercambia en un solo paso. Las 2 réplicas hacen lo mismo y convergen solas.
- **¿Qué es la sombra?** Si existe un `challenger` distinto del champion, la API también lo evalúa después de responder. El usuario solo ve la del champion; las dos quedan en el mismo evento para comparar con datos reales.
- **¿Por qué una cola para el registro?** Escribir en Postgres en cada petición sumaría latencia. La cola se vacía por lotes en otro hilo y, si Postgres falla, la predicción no falla.
- **¿Qué hace el rollback?** Mueve `champion` a la versión de `previous_champion`, deja la retirada como `previous_champion` (así se puede deshacer) y la marca con el tag `rolled_back`. Queda en `audit.model_actions`.
- **¿Qué significa `effect_pct` en `/explain`?** SHAP trabaja en escala log del precio. Una contribución de 0,10 multiplica el precio por e^0,10, es decir +10,5 %.
