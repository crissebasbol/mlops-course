# Pasos del 23 nov (tarde): prueba de carga antes y después del PR de capacidad

Todo se corre en la **.106** (`ssh estudiante@10.43.97.106`), desde el clon del repo de entrega. El orden importa: la línea base se mide **antes** de fusionar el PR `fix/carga-y-historial`, porque ese PR cambia la sombra de la API y hay que comparar el antes con el después.

**Límite:** el PR se fusiona antes del **lunes 23 a las 23:59** (ventana de 72 h). Las pruebas de carga pueden seguir después.

## 0. Preparar la terminal

```bash
cd ~/housing-price-mlops
git switch master && git pull
kubectl config current-context          # housing
./scripts/port_forward.sh status        # 8002 a 8011 en OK; si no: ./scripts/port_forward.sh start
curl -s http://10.43.97.106:8005/health; echo     # champion 4 y sombra 5
```

## 1. Por qué se rechazó la v5

Tenía mejor MAPE que el champion (20,9 % frente a 28,3 %), así que la frenó otra compuerta:

```bash
kubectl -n housing-mlops exec postgres-data-0 -- psql -U postgres -d housing -c "SELECT ingestion_id, promotion_reason FROM audit.batch_runs WHERE ingestion_id = 6"
```

Enviar la salida completa (va al README).

## 2. Línea base de carga (antes de fusionar el PR)

Configuración actual: 2 réplicas de la API con 1 CPU cada una y **sombra en el 100 %** de las predicciones.

### 2.1 Antes de empezar

- Grafana (`http://10.43.97.106:8008`), dashboard **Housing API**, rango **Last 30 minutes**, refresco **10s**.
- No usar la UI web de Locust (`:8010`) mientras corre el script.

### 2.2 Correr (unos 14 minutos)

```bash
nohup ./locust/run_levels.sh 10 25 50 100 > locust/resultados_run.log 2>&1 &
tail -f locust/resultados_run.log        # Ctrl+C solo deja de mirar; la prueba sigue
```

Cada escalón tiene rampa, 3 minutos estables y 30 s de descanso. El log muestra `== rep2_uN: ...` al empezar cada uno.

### 2.3 Capturas

Al **final de cada escalón** (antes del siguiente `==`), una captura de Grafana con:

- peticiones por segundo (total y por réplica);
- latencia de `/predict` p50, p95 y p99;
- tasa de error y peticiones en curso;
- CPU, memoria y throttling de los pods de la API.

Al terminar, una captura del dashboard completo con los 4 escalones.

### 2.4 Al terminar

```bash
column -s, -t < locust/resultados/resumen.csv
kubectl -n housing-mlops top pod -l app=api
kubectl -n housing-mlops get pods -l app=api      # anotar los RESTARTS
```

## 3. Fusionar el PR `fix/carga-y-historial`

En GitHub: aprobar y fusionar con **Create a merge commit**. Cambia tres cosas:

- **Sombra en el 20 % del tráfico:** el replay siempre va en sombra.
- **Sondas de salud con más margen:** `timeoutSeconds` de 5 s (readiness) y 10 s (liveness).
- **Historial de Streamlit:** sin "None" y con el primer y el último ciclo por defecto.

Esperar a que `Build API` y `Build Streamlit` terminen en verde y a que el bot haga sus dos commits (`Imagen api sha-...` e `Imagen streamlit sha-...`). Luego, en la .106:

```bash
git pull
argocd app get serving --refresh | tail -8
kubectl -n housing-mlops rollout status deploy/api
kubectl -n housing-mlops get pods -l app=api -o yaml | grep "image: crissebasbol"
curl -s http://10.43.97.106:8005/model-info | python3 -m json.tool | grep -E "shadow_sample_rate|\"version\""
```

Esperado: imagen nueva en las 2 réplicas y `"shadow_sample_rate": 0.2`. En Streamlit (`:8007`), el historial sin "None".

**Capturas:** el `argocd app get serving` con la sincronización y la página Historial de lotes ya corregida.

## 4. Segunda corrida (después del PR)

Los mismos escalones, para comparar:

```bash
nohup ./locust/run_levels.sh 10 25 50 100 > locust/resultados_run2.log 2>&1 &
tail -f locust/resultados_run2.log
```

Las mismas capturas de Grafana de la sección 2.3. Al terminar:

```bash
column -s, -t < locust/resultados/resumen.csv     # ya tiene las filas de las dos corridas
kubectl -n housing-mlops top pod -l app=api
kubectl -n housing-mlops get pods -l app=api
```

## 5. Qué enviar a Cristhian

1. La salida de la sección 1 (razón del rechazo de la v5).
2. El `resumen.csv` con las dos corridas y las salidas de `kubectl top` y `get pods` de cada una.
3. Las capturas de Grafana de las dos corridas y las de la sección 3.

Con eso se escribe el análisis de carga del README: dónde se satura la API, por qué (CPU por predicción, sombra, throttling) y cuánto mejora con el ajuste.
