# Taller 5 - Pruebas de carga con Locust

Prueba de carga a una API de inferencia que sirve un modelo cargado desde
**MLflow**, para medir cuántos usuarios concurrentes soporta **una réplica**
limitada a **1 CPU y 1 GB** y cuánto cambia la capacidad con **tres réplicas**
detrás de **Nginx**. Se usa el dataset **Covertype** de taller4.

## Arquitectura

La API y todo lo que necesita corren en una VM; Locust corre en **otra VM**, así
la CPU que se gasta simulando usuarios no compite con la de la API.

![Arquitectura](images/architecture.png) 

Flujo:

1. `trainer` entrena dos Random Forest de Covertype, los registra en MLflow como
   versiones de `covertype_rf` y le pone el alias `champion` al mejor.
2. Cada réplica de la `api` descarga el `champion` **al arrancar** y lo deja en
   memoria. Durante la prueba `/predict` no llama a MLflow.
3. Nginx es la única entrada pública y reparte las peticiones entre réplicas.
4. Locust, desde la VM `.106`, genera la carga contra `http://10.43.97.105:8000`.

## Estructura

Cada carpeta es un servicio con su `docker-compose.yml` y su README. 
El `docker-compose.yml` de la raíz los une con `include`. 
Locust tiene su propio compose porque se ejecuta en otra VM.

## Paso a paso

### 1. Construir y publicar la imagen de la API en Docker Hub

```bash
docker login
docker buildx build --platform linux/amd64,linux/arm64 \
  -t crissebasbol/taller5-api:1.0.0 \
  -t crissebasbol/taller5-api:latest \
  --push api
```

En la siguiend imagen se ve la publicación en Docker Hub, con la etiqueta `1.0.0` y `latest`.
![dockerhub](images/01_dockerhub.png)

### 2. Levantar el stack con una réplica

```bash
cd taller_5
docker compose up -d --build --scale api=1
```

La primera vez el `trainer` tarda un par de minutos entrenando.

En la siguiente imagen se ve que la réplica `taller5-api-1` está `healthy`,
trainer se demoró un par de minutos y Nginx ya está listo para recibir peticiones.
![ps_1_replica](images/02_docker_ps_1_replica.png)

### 3. Verificar que todo funciona

Modelo registrado en MLflow (http://10.43.97.105:8004):

A continuación se ve la interfaz web de MLflow mostrando las dos versiones del modelo `covertype_rf`
![ml_flow](images/03_mlflow.png)

Versiones registradas, a través de la API:

```bash
curl http://10.43.97.105:8000/models
```

Llamando a este endpoint se obtiene un JSON con las dos versiones del modelo `covertype_rf`, sus métricas y cuál tiene el alias `champion`.
En la siguiente imagen se ve la salida de `GET /models` mostrando las dos versiones, sus métricas y cuál tiene el alias `champion`.
![models](images/04_api_models.png)

De igual manera si se llama al endpoint de predict usando nginx se obtiene un JSON con el `cover_type` predicho, la `version` del modelo y la `replica` que atendió la petición.
![predict](images/05_api_predict.png)

Límites aplicados a la réplica

```bash
docker inspect taller5-api-1 --format 'cpus={{.HostConfig.NanoCpus}} mem={{.HostConfig.Memory}}'
```
![limits](images/06_limites_replica.png)

### 4. Preparar Locust

Comprobación de que la API responde

```bash
curl http://10.43.97.105:8000/health
```

Construir la imagen de Locust:

```bash
cd mlops-course/taller_5/locust
docker compose build
```
Para observar la UI de Locust:
```bash
docker compose up
```
En la siguiente imagen se ve la interfaz web de Locust mostrando los campos para configurar la prueba de carga, incluyendo el número de usuarios, la tasa de aparición y el host de la API.
![locust_ui](images/07_locust_ui.png)

### 5. Prueba con 1 réplica

Se diseñó un script que captura estadísticas de docker y se ejecuta en la instancia donde API inferencia está corriendo:
```bash
./scripts/docker_stats.sh rep1_u200 140
```

En la instancias donde corre Locust, se ejecuta el script `run_levels.sh` que genera carga de usuarios concurrentes en niveles crecientes.
```bash
./run_levels.sh 1 50 100 200 400 800
```

Por cada nivel `run_levels.sh`:

- Ejecuta `docker compose run --rm --no-deps locust --headless ...` con los
  mismos parámetros.
- Guarda los CSV de Locust en `locust/resultados/rep1_u<usuarios>_*.csv`.
- Guarda la CPU/memoria del propio generador en `stats/locust_rep1_u<usuarios>.csv`.
- Agrega una fila a `locust/resultados/resumen.csv` con RPS, peticiones, % de
  fallos, p50/p95/p99 y si **cumple** el criterio.
- Espera 30 s antes del siguiente nivel.

Variables para ajustar sin tocar el script (deben quedar iguales entre 1 y 3
réplicas): `API_HOST`, `SPAWN_RATE`, `STABLE_SECONDS`, `COOLDOWN`,
`LOCUST_PROCESSES`, `MAX_FAIL_PCT`, `MAX_P95_MS`.

Si la CPU del contenedor de Locust llega a ~100 % (un proceso de Python usa un
solo núcleo), el límite es del generador y no de la API. En ese caso repetir con
`LOCUST_PROCESSES=-1 ./run_levels.sh ...` para usar todos los núcleos de la VM
`.106`.

TODO imagen: `images/08_rep1_run_levels.png` con la salida de `run_levels.sh`
para 1 réplica (tabla final de `resumen.csv`).

TODO imagen: `images/09_rep1_docker_stats.png` con el pico de
`docker_stats.sh` en la VM `.105` en el nivel máximo que cumple y en el primero
que no cumple (la API cerca de 100 % de CPU).

TODO imagen: `images/10_rep1_locust_charts.png` con las gráficas de Locust
(RPS, tiempos de respuesta, usuarios) en el punto de saturación de 1 réplica.

### 6. Escalar a 3 réplicas (VM `.105`)

```bash
docker compose up -d --scale api=3
docker compose ps api
```

Nginx descubre las réplicas nuevas solo (vuelve a resolver `api` cada 5 s). Para
comprobar que reparte, se llama varias veces y el campo `replica` debe cambiar:

```bash
for i in $(seq 6); do curl -s http://10.43.97.105:8000/health; echo; done
```

TODO imagen: `images/11_docker_ps_3_replicas.png` con `taller5-api-1`,
`taller5-api-2` y `taller5-api-3` `healthy`, y la salida del `for` mostrando
tres `replica` distintas.

### 7. Prueba con 3 réplicas

Mismos comandos, mismo `locustfile.py`, misma tasa de aparición, misma ventana y
mismo criterio. Solo cambia el primer argumento:

```bash
# VM .105
./scripts/docker_stats.sh rep3_u600 150
# VM .106
./run_levels.sh 3 200 400 600 800 1200
```

TODO imagen: `images/12_rep3_run_levels.png` con la salida de `run_levels.sh`
para 3 réplicas.

TODO imagen: `images/13_rep3_docker_stats.png` con el pico de `docker_stats.sh`
mostrando las tres réplicas y Nginx en el nivel de saturación.

TODO imagen: `images/14_rep3_locust_charts.png` con las gráficas de Locust en el
punto de saturación de 3 réplicas.

TODO imagen: `images/15_locust_vm_cpu.png` con la CPU de la VM `.106` (por
ejemplo `stats/locust_rep3_u<max>.csv` o `htop`) en el nivel más alto, para
mostrar que el generador no era el límite.

### 8. Apagar

```bash
# VM .105
docker compose down
# Para borrar también los volúmenes (MLflow y MinIO):
docker compose down -v
```

## Resultados

Llenar con `locust/resultados/resumen.csv` (VM `.106`) y `stats/*.csv`
(CPU/memoria de la VM `.105`).

### 1 réplica (1 CPU, 1 GB)

| Usuarios | RPS | Peticiones | Fallos % | p50 (ms) | p95 (ms) | CPU API | RAM API | CPU Locust | Cumple |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 50 | | | | | | | | | |
| 100 | | | | | | | | | |
| 200 | | | | | | | | | |
| 400 | | | | | | | | | |
| 800 | | | | | | | | | |

### 3 réplicas (1 CPU, 1 GB cada una)

| Usuarios | RPS | Peticiones | Fallos % | p50 (ms) | p95 (ms) | CPU API (c/u) | RAM API (c/u) | CPU Nginx | CPU Locust | Cumple |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 200 | | | | | | | | | | |
| 400 | | | | | | | | | | |
| 600 | | | | | | | | | | |
| 800 | | | | | | | | | | |
| 1200 | | | | | | | | | | |

### Comparación

| Métrica | 1 réplica | 3 réplicas | Cambio |
|---------|----------:|-----------:|-------:|
| Concurrencia máxima sostenible (usuarios) | TODO | TODO | TODO % |
| RPS en ese nivel | TODO | TODO | TODO % |
| p95 en ese nivel (ms) | TODO | TODO | |
| Primer nivel que no cumple | TODO | TODO | |

Cambio % = `(3 réplicas - 1 réplica) / 1 réplica × 100`. Un escalado perfecto
sería +200 % (3×).

## Preguntas

**¿Cuál es la concurrencia máxima sostenible y cuántos RPS procesa una réplica
limitada a 1 CPU y 1 GB?**

TODO: último nivel de la tabla de 1 réplica que cumple el criterio, con su RPS.

**¿Cuál es la concurrencia máxima sostenible y cuántos RPS procesan tres réplicas
con esos mismos límites por réplica?**

TODO: último nivel de la tabla de 3 réplicas que cumple el criterio, con su RPS.

**¿En qué porcentaje cambió la capacidad? ¿El aumento fue cercano a tres veces o
aparecieron otros cuellos de botella?**

TODO: usar la tabla de comparación. Si queda lejos de 3×, revisar qué se saturó
en la siguiente pregunta.

**¿Qué recurso se saturó primero y qué evidencia muestran `docker stats`, Locust
y la máquina generadora de carga?**

TODO. Lo que se espera ver si el límite es la API: la CPU de cada réplica llega a
~100 % (1 CPU) mientras la memoria queda muy por debajo de 1 GB; en Locust el RPS
deja de subir aunque aumenten los usuarios y el p95 crece de golpe; la CPU del
contenedor de Locust en `.106` queda lejos de su límite.

**¿Qué servicios adicionales (MLflow, base de datos o balanceador) pudieron
limitar el resultado?**

TODO. Puntos a revisar con la evidencia:

- **MLflow, MinIO y Postgres**: la API solo los usa al arrancar, así que durante
  la prueba su CPU debería quedarse en ~0 % (siempre que nadie llame
  `/models`, que sí consulta MLflow). Esta es la diferencia con taller4,
  donde cada `/predict` consultaba el alias en MLflow y MLflow habría sido el
  cuello de botella.
- **Nginx**: no tiene límite; revisar su CPU en `docker stats` con 3 réplicas.
- **La propia VM `.105`**: si tiene pocos núcleos, o si otro proceso los usa
  durante la prueba, tres réplicas de 1 CPU pueden no recibir 1 CPU completa cada
  una.
- **Locust y la red/VPN**: un solo proceso de Locust usa un núcleo; y la latencia
  entre `.106` y `.105` suma al p95.
