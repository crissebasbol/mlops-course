# Pasos del 23 nov (noche): prueba de carga con la sombra al 20 %

Todo se corre en la **.106** (`ssh estudiante@10.43.97.106`), desde el clon del repo de entrega.

Contexto:
- **Antes:** la referencia es la prueba manual con la UI de Locust (100 usuarios, sombra al 100 %: unos 6 RPS y p50 de 15 s). Ya está en las capturas `locust_03` y `grafana_02`.
- **Después:** el PR #25 dejó la sombra en el 20 % del tráfico y le dio más margen a las sondas de la API. El #26 arregló el permiso de `run_levels.sh`.

Esta corrida mide el **después**.

## 0. Preparar la terminal

```bash
cd ~/housing-price-mlops
git switch master && git pull
ls -l locust/run_levels.sh               # debe tener x (-rwxr-xr-x)
kubectl config current-context           # housing
./scripts/port_forward.sh status         # 8002 a 8011 en OK; si no: ./scripts/port_forward.sh start
```

## 1. Verificar que el #25 quedó desplegado

```bash
argocd app get serving --refresh | tail -8
kubectl -n housing-mlops get pods -l app=api -o yaml | grep "image: crissebasbol"     # housing-api:sha-587b565
kubectl -n housing-mlops get pods -l app=streamlit -o yaml | grep "image: crissebasbol" # housing-streamlit:sha-587b565
curl -s http://10.43.97.106:8005/model-info | python3 -m json.tool | grep -E "shadow_sample_rate|\"version\""
```

Esperado: las dos imágenes con `sha-587b565`, `"shadow_sample_rate": 0.2`, champion en la versión 4 y sombra en la 5.

**Capturas:**
- el `argocd app get serving` con la sincronización;
- Streamlit (`:8007`), página **Historial de lotes**: sin "None" y con los ciclos 1 y 12 (o el último) por defecto.

## 2. Prueba de carga (unos 14 minutos)

### 2.1 Antes de empezar

- Grafana (`http://10.43.97.106:8008`), dashboard **Housing API**, rango **Last 30 minutes**, refresco **10s**.
- No usar la UI web de Locust (`:8010`) mientras corre el script.

### 2.2 Correr

```bash
nohup ./locust/run_levels.sh 10 25 50 100 > locust/resultados_run.log 2>&1 &
tail -f locust/resultados_run.log        # Ctrl+C solo deja de mirar; la prueba sigue
```

Cada escalón tiene rampa, 3 minutos estables y 30 s de descanso. El log muestra `== rep2_uN: ...` al empezar cada uno.

### 2.3 Capturas

Al **final de cada escalón** (antes del siguiente `==`), una captura de Grafana con:

- peticiones por segundo (total y por réplica);
- latencia de `/predict` p50, p95 y p99;
- latencia del modelo por rol (champion y sombra);
- tasa de error y peticiones en curso;
- CPU, memoria y throttling de los pods de la API.

Al terminar, una captura del dashboard completo con los 4 escalones.

### 2.4 Al terminar

```bash
column -s, -t < locust/resultados/resumen.csv
kubectl -n housing-mlops top pod -l app=api
kubectl -n housing-mlops get pods -l app=api      # anotar los RESTARTS
```

## 3. Qué enviar a Cristhian

1. La salida de la sección 1 y las dos capturas.
2. La salida de la sección 2.4 (`resumen.csv`, `top` y `get pods`).
3. Las capturas de Grafana de cada escalón y la del final.

Con eso se escribe el análisis de carga del README: capacidad por réplica, dónde se satura y por qué (CPU por predicción, sombra, throttling), la comparación con la prueba manual y qué conviene ajustar.
