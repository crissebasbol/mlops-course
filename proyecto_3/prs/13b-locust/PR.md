# PR 13b: Locust y prueba de carga (Fabián Ramírez)

**Depende del 13a fusionado** (Prometheus y Grafana arriba) y de que la API tenga champion. Usa la imagen oficial `locustio/locust:2.46.7`; el `locustfile.py` va en un ConfigMap, así que tampoco hay imagen propia.

Validado en local:

- `ruff` del `locustfile.py` y `shellcheck` de `run_levels.sh`.
- `kubectl kustomize observability` (con Locust) y `kubeconform`: 16 recursos válidos.
- Corrida headless de 90 s con 20 usuarios contra la API real en Docker:

| Tipo | Peticiones | Fallos | Mediana | p95 |
|---|---|---|---|---|
| `/predict` | 1.025 | 0 | 350 ms | 950 ms |
| `/predict (replay)` | 251 | 0 | 360 ms | 1.100 ms |
| Total | 1.276 | 0 | | |

La muestra de 5.000 filas se descargó con el usuario `locust` de MinIO, que no puede listar el bucket.

## Pasos (git)

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/locust

# copiar locust/ (nuevo) y observability/kustomization.yaml (solo agrega "- ../locust")

git add locust/locustfile.py locust/k8s locust/kustomization.yaml locust/README.md
git commit -m "Locust con usuarios de predicción y replay"
git add locust/run_levels.sh
git commit -m "Prueba de carga por escalones"
git add observability/kustomization.yaml
git commit -m "Locust en la app de observabilidad"
git push -u origin feature/locust
```

Comprobar que `locust/run_levels.sh` quede con permiso de ejecución (`git ls-files -s locust/run_levels.sh` debe empezar con `100755`; si no, `git update-index --chmod=+x locust/run_levels.sh`).

**Título del PR:** `Locust: usuarios de predicción y replay, y prueba por escalones`

**Qué cambia**

- `locust/locustfile.py`: dos tipos de usuario, ambos con espera de 0,5 a 1,5 s; una respuesta distinta de 200 cuenta como fallo.
  - `PredictUser` (peso 4): filas de la muestra con `X-Traffic-Source: locust`.
  - `ReplayUser` (peso 1): filas holdout con `X-Traffic-Source: replay` y `X-Replay-Row`, para el MAPE en línea.
- `locust/k8s/deployment.yaml`:
  - init container que descarga `s3://datasets/replay/holdout_sample.json` con el usuario `locust` (solo lectura de `datasets/replay/*`) y reintenta cada 30 s si todavía no existe;
  - Locust con su UI web, recursos, probes y nodo de datos, para no competir por CPU con la API.
- `locust/run_levels.sh`:
  - escalones de 10, 50, 100, 200 y 300 usuarios, 3 min estables cada uno, corridos headless dentro del pod;
  - guarda `kubectl top` de la API y una fila por escalón en `locust/resultados/resumen.csv` (RPS, fallos, p50/p95/p99, si cumple, versión champion e inicio/fin para ubicarlo en Grafana);
  - antes de empezar verifica que haya champion.
- `observability/kustomization.yaml`: incluye `../locust`, así Argo despliega Locust en la app `observability`.

**Por qué**

Sección de pruebas de carga del enunciado: Locust desplegado en Kubernetes con el `locustfile` en el repo, ejecutado contra FastAPI, con evidencia del efecto de la carga en Grafana.

**Cómo se probó**

- [x] `ruff`, `shellcheck`, `kubectl kustomize` y `kubeconform` (16 recursos)
- [x] Corrida de 90 s con 20 usuarios en Docker: 1.276 peticiones, 0 fallos
- [ ] Prueba por escalones en el clúster (completar con `resumen.csv`)

**Checklist**

- [x] Sin secretos en el diff (las credenciales de MinIO llegan del Secret `minio-locust`)
- [x] Contenedores nuevos con `requests`, `limits` y probes

## Después de fusionar (en la .106)

```bash
cd ~/housing-price-mlops && git switch master && git pull
argocd app get observability --refresh | tail -8
kubectl -n housing-mlops get pods -o wide | grep locust
kubectl -n housing-mlops logs deploy/locust -c replay-sample
kubectl -n housing-mlops logs deploy/locust -c locust | grep "Muestra de replay"
```

| Qué | Dónde | Esperado |
|---|---|---|
| Pod | `kubectl get pods -o wide` | `locust` `Running` en `nodo-data` |
| Muestra | log de `locust` | `Muestra de replay: 5000 filas holdout` |
| UI | `http://10.43.97.106:8010` | Locust con host `http://api:8000` |

### Prueba de carga

1. Abrir Grafana (`:8008`, dashboard Housing API) en *Last 30 minutes* con refresco de 10 s.
2. Correr en la .106:

```bash
./locust/run_levels.sh        # unos 20 minutos para los 5 escalones
```

3. Con los segundos de inicio y fin de `resumen.csv`, tomar las capturas de Grafana de cada escalón:
   - peticiones por segundo;
   - latencia p50/p95/p99;
   - errores;
   - CPU y throttling por pod;
   - memoria.
4. Subir `locust/resultados/` en un PR corto, porque son la evidencia de la prueba.

**Capturas para el README:**
- la corrida de Locust (usuarios, RPS y fallos; evidencia 18);
- Grafana durante los escalones (evidencia 19);
- la tabla de `resumen.csv`;
- el panel de MAPE en línea del replay.

## Para explicarlo

- **¿Por qué dos tipos de usuario?** `PredictUser` simula tráfico normal. `ReplayUser` manda filas de precio conocido, para medir el error del modelo en producción mientras hay carga.
- **¿Por qué Locust en el nodo de datos?** Si generara la carga en el mismo nodo que la API, le quitaría CPU y la latencia medida sería peor que la real.
- **¿Qué mirar en Grafana?** Cuándo empieza a subir la latencia p95, si aparecen errores, si la CPU llega al límite de 1 core por réplica (y el throttling sube) y si la memoria se mantiene estable. Con eso se justifica si 2 réplicas y esos límites alcanzan.
