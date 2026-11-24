# Guion del video de sustentación (máximo 10 minutos)

El enunciado (sección 10) pide que el video muestre como mínimo: organización del repositorio, arquitectura y comunicación entre componentes, workflows de GitHub Actions, despliegue con Argo CD, ejecución del DAG y sus bifurcaciones, MLflow, un caso que entrena y promueve, un caso que entrena y no promueve (o no entrena), FastAPI y Streamlit para inferencia, historial en Streamlit, y Locust con su efecto en Grafana. Este guion cubre los 11 puntos en **9 min 30 s**, con margen.

## Reparto

| Bloque | Tiempo | Quién | Puntos del enunciado | Sección del README |
|---|---|---|---|---|
| 1. Presentación, arquitectura y repositorio | 0:00-1:40 | Cristhian Bolaños | Organización del repo, arquitectura | Inicio, 1 |
| 2. CI/CD, Argo CD y Kubernetes | 1:40-3:10 | Cristian Organista | Actions, Argo CD | 11, 12 |
| 3. DAG de Airflow y decisión de entrenar | 3:10-4:40 | Cristian Organista | DAG y bifurcaciones, caso que no entrena | 4, 7 |
| 4. MLflow y promoción | 4:40-6:30 | Cristhian Bolaños | MLflow, caso promovido, caso rechazado | 5, 7, 8 |
| 5. FastAPI y Streamlit | 6:30-8:00 | Fabián Ramírez | Inferencia, historial en Streamlit | 9, 10 |
| 6. Prueba de carga y cierre | 8:00-9:30 | Fabián Ramírez | Locust y Grafana | 13, 14 |

Cada uno graba su bloque por separado (pantalla y voz) y se unen al final. Así se repite solo el bloque que salga mal.

## Antes de grabar (una sola vez)

- En la .106: `cd ~/housing-price-mlops && git pull && ./scripts/port_forward.sh status`. Los puertos del 8002 al 8011 deben estar en OK.
- Sesiones iniciadas en Airflow (`:8002`), Argo CD (`:8006`) y Grafana (`:8008`). **Ninguna contraseña ni token en pantalla**, ni en la terminal ni en el navegador.
- Navegador sin marcadores personales a la vista, zoom al 110-125 % para que se lea, notificaciones silenciadas y sin el aviso de "estás compartiendo pantalla".
- Pestañas listas para cada bloque (están en cada bloque abajo).
- **No hacer commits ni merges durante la grabación.** El último merge del proyecto debe ser el del enlace del video, el jueves.

---

## Bloque 1. Presentación, arquitectura y repositorio (Cristhian Bolaños, 1:40)

**Pestañas:** el repo en GitHub (vista de archivos) y el mapa interactivo (https://crissebasbol.github.io/housing-price-mlops/arquitectura.html) con zoom al 80 % para que quepa entero en 1920x1080.

**Mostrar y decir:**

1. **(0:00-0:25) Presentación.** "Somos Cristhian Bolaños, Cristian Organista y Fabián Ramírez. Construimos una plataforma de MLOps que predice el precio de viviendas y, sobre todo, **decide sola** cuándo reentrenar, si un modelo nuevo es mejor que el que está en producción y cómo cambiarlo sin redesplegar la API. Todo corre en Kubernetes y se despliega desde este repositorio con Argo CD."
2. **(0:25-1:10) Arquitectura**, sobre el mapa interactivo:
   - Botón **Un cambio en Git** (se reproduce solo, un paso cada 4 s): "Arriba, el ciclo GitOps: un push dispara GitHub Actions, que publica la imagen en DockerHub con el SHA del commit y escribe el tag nuevo en el manifiesto; Argo CD ve ese commit y sincroniza el clúster."
   - "El clúster tiene dos nodos. En `nodo-data` está la ingesta y el entrenamiento: la API de datos, Airflow, PostgreSQL con RAW, CLEAN y auditoría, MinIO y MLflow. En `nodo-serving`, la inferencia y la observabilidad: FastAPI, Streamlit, Prometheus y Grafana."
   - Botón **Un lote de datos**: "Cada 15 minutos Airflow pide un lote, lo valida, decide si entrenar y, si el candidato pasa las compuertas, mueve el alias `champion` en MLflow. La API revisa ese alias y carga el modelo nuevo sin reiniciarse."
   - Si sobra tiempo, tocar **FastAPI** para mostrar el panel con sus réplicas y recursos. Fabián retoma el mapa al abrir los bloques 5 y 6.
3. **(1:10-1:40) Organización del repositorio**, recorriendo las carpetas en GitHub:
   - "`housing_ml` es el paquete con la lógica del modelo: esquema, calidad, drift, decisión y compuertas. Lo usan igual Airflow y la API, con las mismas versiones."
   - "`airflow`, `api` y `streamlit` tienen el código y el Dockerfile de cada servicio; `database`, `minio`, `mlflow` y `observability`, sus manifiestos; `argocd`, las apps; `.github/workflows`, la CI. El README es el informe, con la bitácora y la evidencia de cada etapa."

## Bloque 2. CI/CD, Argo CD y Kubernetes (Cristian Organista, 1:30)

**Pestañas:** GitHub Actions; una corrida de `Build Airflow` o `Build API`; DockerHub (`crissebasbol/housing-api` o `housing-airflow`, pestaña Tags); el commit del bot; Argo CD (Applications y la app `serving` o `airflow`); terminal en la .106.

**Mostrar y decir:**

1. **(1:40-2:15) GitHub Actions y DockerHub.** Abrir la lista de Actions: "Cada PR corre la CI: ruff, 89 pruebas y la validación de todos los manifiestos con kubeconform." Abrir una corrida de build: "Al fusionar, se construye la imagen y se publica con el SHA del commit." Mostrar el tag en DockerHub y el commit del bot: "Este commit `Imagen api sha-...` lo hace el workflow: cambia el tag en el manifiesto."
2. **(2:15-2:50) Argo CD.** Applications: "Aplicamos una sola app a mano, `housing-root`; ella crea las demás desde Git: plataforma de datos, Airflow, serving y observabilidad, todas Synced y Healthy." Abrir **History and Rollback** de `airflow` o `serving`: "Aquí se ve la sincronización con el commit del bot: el cambio en Git llegó solo al clúster."
3. **(2:50-3:10) Kubernetes.** En la terminal:
   ```bash
   kubectl -n housing-mlops get pods -o wide
   kubectl -n housing-mlops get hpa api
   ```
   "Cada pod en su nodo; todos con requests, limits y probes; las contraseñas en Secrets, nunca en el repo. La API tiene un autoescalado de 2 a 3 réplicas por CPU."

## Bloque 3. DAG de Airflow y decisión de entrenar (Cristian Organista, 1:30)

**Pestañas:** Airflow (`:8002`), DAG `housing_pipeline` en vista **Graph** y en vista **Grid**; Streamlit (`:8007`), Historial de lotes.

**Mostrar y decir:**

1. **(3:10-3:50) El DAG y sus bifurcaciones**, en la vista Graph:
   - "Una ejecución es una petición a la API de datos, es decir, un lote. Son 26 tareas de responsabilidad única."
   - "Hay tres bifurcaciones. `route_batch` separa un lote nuevo, uno repetido y el fin de datos. `decide_training` elige entre entrenar o no. `decide_promotion` elige entre promover o rechazar."
   - "Antes de pedir un lote, `check_dependencies` revisa que todo esté arriba, para no gastar lotes con el sistema caído."
2. **(3:50-4:20) Ejecución**, en la vista Grid: mostrar varias corridas con ramas distintas. "Lleva corriendo cada 15 minutos desde el 22 de noviembre. Aquí se ven corridas que promueven, que rechazan, que no entrenan, el fin de datos y los lotes repetidos que solo vigilan al modelo."
3. **(4:20-4:40) Caso que no entrena**, en Streamlit, Historial: señalar el ingreso 4 (lote 3). "Este lote trae 4.054 filas, el 1 % de lo acumulado. La regla exige al menos 10 mil y el 5 %: no entrena, y la razón queda registrada. Que no se entrene no depende de la hora ni del número de lotes: depende de qué trae el lote, es decir, drift, categorías nuevas, crecimiento del volumen o degradación del modelo."

## Bloque 4. MLflow y promoción (Cristhian Bolaños, 1:50)

**Pestañas:** MLflow (`:8003`), experimento `housing-price` (Training runs); el run `c1-b4-...` (Overview y Artifacts); la página de modelos (`http://10.43.97.106:8003/#/models`, o el menú de modelos); Streamlit, Historial de lotes, "Detalle de un ingreso" del 5 y del 6 (Compuertas).

**Mostrar y decir:**

1. **(4:40-5:20) Registro en MLflow.** La lista de runs: "Un run por entrenamiento, cada uno con su versión registrada." Abrir `c1-b4`: "Cada run guarda el lote y los lotes usados, la huella de los datos, el commit de la imagen que entrenó, la razón del entrenamiento y de la promoción, métricas en train, validación, test y holdout, y artefactos como SHAP." Mostrar el beeswarm de SHAP en Artifacts.
2. **(5:20-5:55) Caso que entrena y promueve: ingreso 5, lote 4.** Abrir el detalle de Compuertas en Streamlit: "El lote 4 trae precios entre 300 y 500 mil dólares, un rango que nadie había visto: drift del precio con PSI de 8. El candidato baja el MAPE de 28,7 a 20,5 % sobre el mismo holdout que el modelo productivo. Pasa las seis compuertas, entre ellas la significancia por bootstrap, y se promueve como versión 4."
3. **(5:55-6:30) Caso que entrena y no promueve: ingreso 6, lote 5.** "La versión 5 era todavía mejor en error, 20,9 frente a 28,3 %, pero tarda 152 milisegundos por predicción y el presupuesto es 150. La compuerta de latencia la rechaza. Queda registrada como challenger y la API la corre en sombra, pero no reemplaza al champion. Promover es mover el alias `champion` en el registro, no tocar la API."

## Bloque 5. FastAPI y Streamlit (Fabián Ramírez, 1:30)

**Pestañas:** el mapa en el recorrido de una predicción (https://crissebasbol.github.io/housing-price-mlops/arquitectura.html#inferencia, zoom al 80 %); Swagger de la API (`:8005/docs`); `:8005/model-info`; Streamlit (`:8007`) en Predicción y en Modelo en producción.

**Mostrar y decir:**

1. **(6:30-7:05) Recorrido y FastAPI.** Abrir el mapa en `#inferencia` y dejar que avancen los dos primeros pasos (unos 8 s): "El usuario entra a Streamlit y Streamlit le envía la propiedad a la API, que responde con el champion y registra cada inferencia." Pasar a Swagger, ejecutar `POST /predict` con el ejemplo: "La respuesta trae el precio, la versión y el alias del modelo." Abrir `/model-info`: "La API nunca tiene una versión escrita: carga el alias `champion` de MLflow y el challenger en sombra. Revisa los alias cada 30 segundos y, si cambian, carga el modelo nuevo y lo reemplaza de forma atómica, sin reiniciar. Si la descarga falla, sigue con el anterior. Cada inferencia queda registrada en PostgreSQL."
2. **(7:05-7:30) Streamlit, inferencia.** Predecir con el formulario y pulsar "¿Por qué este precio?": "La interfaz siempre pasa por la API, así que muestra la misma versión que producción, y explica la predicción con SHAP."
3. **(7:30-8:00) Streamlit, historial y modelo.** Página Historial de lotes: "Cada lote con su decisión, la razón, el MAPE del candidato frente al productivo y el enlace a MLflow." Página Modelo en producción: "Aquí se ven las recargas: las dos réplicas cargaron las versiones 2, 3 y 4 sin reiniciarse, con el mismo nombre de pod."

## Bloque 6. Prueba de carga y cierre (Fabián Ramírez, 1:30)

**Pestañas:** el mapa en el recorrido de la carga (https://crissebasbol.github.io/housing-price-mlops/arquitectura.html#carga, zoom al 80 %); Grafana, dashboard **Housing API**, con el rango de las pruebas del 23 de noviembre (de 18:45 a 19:50 aproximadamente, o "Last 2 days" y hacer zoom); Locust (`:8010`) o la terminal con el `resumen.csv`.

**Mostrar y decir:**

1. **(8:00-8:20) Cómo se hizo.** Abrir el mapa en `#carga`; el primer paso resalta la flecha de Locust a la API mientras se dice: "Locust corre en el clúster, en otro nodo, con dos tipos de usuario: predicciones normales y filas del holdout con su precio real, para medir el error en línea. Corrimos escalones de 10, 25, 50 y 100 usuarios."
2. **(8:20-9:05) Qué se vio en Grafana**, recorriendo los paneles en el rango de las pruebas:
   - "Con dos réplicas fijas, la API se estancó en unos 8 peticiones por segundo: más usuarios solo alargaban la cola, de 300 milisegundos a 11 segundos de mediana."
   - "En los recursos se ve por qué: la CPU de cada réplica pegada a su límite. Cada predicción cuesta unos 250 milisegundos de CPU."
   - "Agregamos un autoescalado y el HPA subió a tres réplicas: unas 11 peticiones por segundo, un 30 % más, sin fallos ni reinicios."
   - "Y el replay muestra que la sombra, la versión 5, se equivoca menos que el champion también en producción. Es el compromiso entre precisión y costo que hizo que la compuerta de latencia la rechazara."
3. **(9:05-9:30) Cierre.** "Todo el detalle, las decisiones, los problemas que encontramos y la evidencia de cada etapa están en el README del repositorio. Gracias."

## Después de grabar

1. Unir los bloques y revisar que dure menos de 10 minutos.
2. Subir a YouTube como **Público** o **No listado** (que se abra sin iniciar sesión), con el título "Housing Price MLOps: proyecto final MLOps PUJ" y el enlace al repositorio en la descripción.
3. Pasar el enlace a Cristhian. El PR con el enlace en el README va el **jueves 26** y debe ser el último merge del proyecto.
