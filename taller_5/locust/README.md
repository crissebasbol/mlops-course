# Locust

Genera la carga contra la API de inferencia. Corre en la VM 
`10.43.97.106`, separada de la VM de la API `10.43.97.105`, para que la CPU
usada para simular usuarios no compita con la de las réplicas.

Tiene su propio `docker-compose.yml` y no está
incluido en el compose raíz de `taller_5`, porque se ejecuta en otra máquina.

## Servicio

UI: http://10.43.97.106:8006

## locustfile.py

- `wait_time = between(1, 2.5)`: cada usuario espera entre 1 y 2.5 s entre
  peticiones. Por eso **usuarios ≠ RPS**: un usuario hace como mucho ~0.57
  peticiones por segundo.
- Solo llama `/predict`, que usa el modelo en memoria.
- Con `catch_response=True` marca como **fallo**, aparte de los códigos distintos
  de 200.

## Uso

```bash
curl http://10.43.97.105:8000/health
docker compose build
```

### Interfaz web (exploración)

Abrir http://10.43.97.106:8006. El host ya viene configurado como
`http://10.43.97.105:8000`.

### Variables

Se pueden cambiar sin editar el script.

| Variable           | Por defecto                 | Para qué sirve |
|--------------------|-----------------------------|----------------|
| `API_HOST`         | `http://10.43.97.105:8000`  | Nginx de la VM de la API. |
| `SPAWN_RATE`       | `20`                        | Usuarios nuevos por segundo durante la rampa. |
| `STABLE_SECONDS`   | `120`                       | Duración de la ventana medida después de la rampa. |
| `COOLDOWN`         | `30`                        | Pausa entre niveles. |

### Niveles reproducibles (`run_levels.sh`)

```bash
./run_levels.sh <replicas> <usuarios> [usuarios ...]
./run_levels.sh 1 10 30 60 100 150 200 300 400
./run_levels.sh 3 10 30 60 100 150 200 300 400
```

Las dos pruebas usan los mismos niveles para poder compararlas nivel por nivel.
Cada fila de `resultados/resumen.csv` incluye `inicio_epoch` y `fin_epoch`, la
ventana estable del nivel, que `../scripts/stats_por_nivel.sh` usa para cruzarla
con `docker stats` de la VM de la API. Si `resumen.csv` tiene el formato anterior
(sin esas columnas), el script se detiene y pide moverlo o borrarlo.

El primer argumento solo sirve para nombrar los archivos (`rep1_...`,
`rep3_...`).

Por cada nivel el script:

1. Calcula la rampa (`usuarios / SPAWN_RATE`) y corre
   `--run-time = rampa + STABLE_SECONDS`.
2. Ejecuta `docker compose run --rm --no-deps locust --headless ...` con
   `--reset-stats`, que pone en cero las estadísticas cuando terminan de
   aparecer los usuarios. Así los CSV solo cubren la ventana estable.
3. En paralelo guarda la CPU y la memoria del propio Locust con
   `../scripts/docker_stats.sh` en `../stats/locust_rep<N>_u<usuarios>.csv`.
4. Lee la fila `Aggregated` de `resultados/rep<N>_u<usuarios>_stats.csv` y
   agrega una fila a `resultados/resumen.csv` con RPS, peticiones, fallos,
   p50/p95/p99 y si **cumple** el criterio.
5. Espera `COOLDOWN` segundos antes del siguiente nivel.

## Resultados

Por cada nivel, en `resultados/`:

| Archivo | Contenido |
|---------|-----------|
| `rep<N>_u<usuarios>_stats.csv` | Totales de la ventana estable (la fila `Aggregated` es la que usa el resumen). |
| `rep<N>_u<usuarios>_stats_history.csv` | Serie en el tiempo (RPS, percentiles, usuarios). |
| `rep<N>_u<usuarios>_failures.csv` | Fallos agrupados por mensaje (útil para ver si son 502, timeouts, etc.). |
| `rep<N>_u<usuarios>_exceptions.csv` | Excepciones del propio Locust. |
| `resumen.csv` | Una fila por nivel: `replicas,usuarios,rps,peticiones,fallos,fallos_pct,p50_ms,p95_ms,p99_ms,cumple`. |
