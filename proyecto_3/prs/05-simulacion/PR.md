# PR 5: simulación offline de los lotes (Fabián Ramírez)

Depende de los PRs 3 y 4, ya fusionados. Puede abrirse ya.

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/simulacion

# copiar la carpeta scripts/ de este directorio sobre la raíz del repo
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Correr la simulación con los lotes reales (Docker en el computador; los datos quedan en `data/`, que está en `.gitignore` y nunca se sube):

```bash
docker run -d --rm --name data-api --platform linux/amd64 -p 8089:80 cristiandiaz13/mlops-puj:data-api-pf-v2
uv run python scripts/fetch_batches.py --api-url http://localhost:8089 --out data/batches
uv run python scripts/simulate_batches.py --batches-dir data/batches --out data/simulation
docker stop data-api
```

Guardar la tabla final que imprime (`data/simulation/results.md`) y el log: van a la sección "Calibración" del README.

```bash
git add scripts/fetch_batches.py scripts/simulate_batches.py
git commit -m "Descarga de lotes y simulación offline del pipeline"
git push -u origin feature/simulacion
```

**Título del PR:** `Simulación offline del pipeline con los lotes reales`

**Qué cambia**

- `scripts/fetch_batches.py`: descarga todos los lotes de una instancia local de la API de datos hasta recibir el HTTP 400 de fin de datos.
- `scripts/simulate_batches.py`: aplica la misma lógica del DAG (paquete `housing_ml`, sin Airflow ni MLflow) sobre los lotes: validación, drift, decisión de entrenamiento, entrenamiento, compuertas de promoción y un segundo ciclo con lotes repetidos (monitoreo). Mide tiempo de entrenamiento, latencia y memoria.

**Por qué**

Calibrar los umbrales y conocer la historia esperada antes de desplegar, y dimensionar los recursos de Airflow.

**Cómo se probó**

Corrida completa con los 6 lotes del grupo 1 (pegar aquí la tabla de `results.md`).

## Para explicarlo

Resultado de referencia (corrida del 21 nov):

| Lote | Entrenamiento | Promoción |
|---|---|---|
| 0 | Línea base | Se promueve |
| 1 | Drift en tamaño, camas y baños; degradación del productivo | Se promueve (-15 % de MAPE) |
| 2 | Categoría nueva `sold`; volumen +137 % | Se promueve (-7 %) |
| 3 | No entrena: lote pequeño (1 % del acumulado) | - |
| 4 | Drift extremo del precio | Se promueve (-28 %) |
| 5 | Drift extremo del precio | Se promueve (-26 %) |

La simulación encontró dos problemas que se corrigieron en el PR 4:

1. **Latencia:** todos los candidatos se rechazaban por superar 50 ms por predicción. Causa: `TargetEncoder.transform` de scikit-learn tarda ~60 ms por fila con ~100 mil categorías, y HistGB con varios hilos pierde tiempo coordinándolos para una sola fila. Solución: encoder con diccionarios y 1 hilo al servir (p95 de 10 a 27 ms).
2. **Segmentos:** los lotes 4 y 5 se rechazaban porque las casas de menos de 300 mil empeoraban, aunque el total mejoraba 28 % y 48 %. Causa: ese segmento se define con el precio real (el target) y favorece al modelo que solo conoce precios bajos. Solución: la compuerta bloquea por variables disponibles al predecir (estado, `status`, tamaño) y la banda de precio queda como diagnóstico.
