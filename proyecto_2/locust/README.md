# locust

Imagen `crissebasbol/proyecto2-locust` con `locustfile.py`: cada usuario envía a `/predict`
un registro real tomado de `examples.json`, con `wait_time` de 1 a 2.5 s, y marca como fallo
cualquier respuesta distinta de 200 o sin predicción.

Corre como Deployment en el nodo `data`, lejos de la API (nodo `serving`). La UI queda en
http://10.43.97.106:8010 y apunta a `http://api:8000` (Service que reparte entre réplicas).

`run_levels.sh` corre los niveles en modo headless dentro del pod con `kubectl exec`, copia
los CSV a `resultados/` y agrega una fila por nivel a `resultados/resumen.csv`. También
guarda `kubectl top` de los pods de la API durante cada nivel.

```bash
./run_levels.sh 10 30 60 100 150 200 300
SPAWN_RATE=10 STABLE_SECONDS=180 ./run_levels.sh 50 100
```
