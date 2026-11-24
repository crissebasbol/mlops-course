# Guion del video de sustentación (máximo 10 minutos)

El enunciado (sección 10) pide que el video muestre como mínimo: organización del repositorio, arquitectura y comunicación entre componentes, workflows de GitHub Actions, despliegue con Argo CD, ejecución del DAG y sus bifurcaciones, MLflow, un caso que entrena y promueve, un caso que entrena y no promueve (o no entrena), FastAPI y Streamlit para inferencia, historial en Streamlit, y Locust con su efecto en Grafana. Este guion cubre los 11 puntos en **9 min 25 s**, con margen.

## Reparto

| Parte | Tiempo | Quién | Puntos del enunciado | Sección del README | ¿Necesita la VPN? |
|---|---|---|---|---|---|
| 1. El problema y lo que hizo el sistema | 0:00-2:40 | Fabián Ramírez | Streamlit para inferencia, FastAPI, historial en Streamlit, casos que no entrena, que promueve y que se rechaza | Inicio, 9, 10 | Sí |
| 2. Cómo está hecho y por qué decide | 2:40-5:40 | Cristhian Bolaños | Arquitectura y comunicación, organización del repo, reglas de entrenamiento y compuertas, GitHub Actions | 1, 4, 5, 7, 11 | No: todo es público |
| 3. Cómo corre en el clúster y cuánto aguanta | 5:40-9:25 | Cristian Organista | Argo CD, Kubernetes, ejecución del DAG, MLflow, Locust y Grafana | 8, 11, 12, 13, 14 | Sí |

El video va de afuera hacia adentro: primero qué problema resuelve y qué hizo el sistema con cada lote, luego cómo está hecho y por qué decidió así, y al final cómo corre en el clúster y cuánto aguanta. Cada integrante expone una sola parte, de corrido. Los casos que Fabián señala en el historial son los que Cristhian explica, y el commit con el que Cristhian termina es el que Argo CD sincroniza al empezar la parte de Organista.

Cada uno graba su parte en una toma (pantalla y voz) y se unen al final; si algo sale mal, se repite solo esa parte. Cada parte termina con una frase que le pasa la palabra al siguiente, para que el corte no quede en seco.

## Antes de grabar (una sola vez)

- **Fabián y Organista**, en la .106: `cd ~/housing-price-mlops && git pull && ./scripts/port_forward.sh status`. Los puertos del 8002 al 8011 deben estar en OK. Sesiones iniciadas en Airflow (`:8002`), Argo CD (`:8006`) y Grafana (`:8008`).
- **Cristhian** no necesita la VPN: el mapa, el repo, el README, GitHub Actions y DockerHub son públicos.
- **Ninguna contraseña ni token en pantalla**, ni en la terminal ni en el navegador.
- Navegador sin marcadores personales a la vista, zoom al 110-125 % para que se lea (el mapa interactivo, al 80 % para que quepa entero en 1920x1080), notificaciones silenciadas y sin el aviso de "estás compartiendo pantalla".
- Pestañas abiertas en el orden de cada parte (están al inicio de cada una), para pasar de una a otra sin buscar.
- Mapa interactivo: https://crissebasbol.github.io/housing-price-mlops/arquitectura.html. Con `#gitops`, `#lote`, `#inferencia` o `#carga` al final, abre ese recorrido y lo reproduce solo, un paso cada 4 s.
- **No hacer commits ni merges durante la grabación.** El último merge del proyecto debe ser el del enlace del video, el jueves.

---

## Parte 1. El problema y lo que hizo el sistema (Fabián Ramírez, 0:00-2:40)

**Pestañas, en orden:** Streamlit (`:8007`) en Predicción; Swagger de la API (`:8005/docs`); `:8005/model-info`; Streamlit en Historial de lotes.

**Mostrar y decir:**

1. **(0:00-0:30) Presentación y problema**, con Streamlit abierto en Predicción:
   - "Somos Fabián Ramírez, Cristhian Bolaños y Cristian Organista."
   - "El problema: estimar el precio de venta de una vivienda a partir de su ubicación (estado, ciudad y código postal), su tamaño, habitaciones, baños, terreno y la inmobiliaria que la vende."
   - "Los datos no llegan de una vez: llegan por lotes desde una API, y cambian. En un lote aparecen viviendas vendidas que antes no existían; en otro, precios en un rango que nunca habíamos visto. Un modelo entrenado una sola vez se queda viejo."
   - "Construimos una plataforma que decide sola cuándo reentrenar, si el modelo nuevo es mejor que el que está en producción y cómo cambiarlo sin redesplegar nada. Esto es lo que ve el usuario."
2. **(0:30-1:10) Predicción.** Llenar el formulario y pulsar Predecir: "El precio estimado, con la versión del modelo que lo calculó y su alias." Pulsar "¿Por qué este precio?": "SHAP muestra cuánto sube o baja el precio cada característica de esta vivienda." Enviar un precio real: "Si el usuario conoce el precio real, lo envía y queda guardado junto a la predicción."
3. **(1:10-1:40) FastAPI.** En Swagger, ejecutar `POST /predict` con el ejemplo: "La interfaz nunca carga el modelo: todo pasa por esta API, que responde el precio, la versión y el alias." Abrir `/model-info`: "La API no tiene una versión escrita en el código: sirve la que tenga el alias `champion` en MLflow y prueba en sombra el `challenger`, sin que el usuario lo vea. Cada inferencia queda registrada en PostgreSQL."
4. **(1:40-2:40) Historial de lotes y paso a la parte 2.** "Así se ve el problema en el tiempo: cada lote que llegó, qué señales traía y qué decidió el sistema, con su razón y el error del candidato frente al modelo en producción." Señalar tres filas del primer ciclo:
   - Ingreso 4 (lote 3): "Este lote no entrenó."
   - Ingreso 5 (lote 4): "Este entrenó por drift y su modelo, la versión 4, quedó en producción. Es la que sirve hoy la API."
   - Ingreso 6 (lote 5): "Este también entrenó, y su modelo era más preciso, pero se rechazó."
   - Mostrar la gráfica de MAPE por ingreso y cerrar con: "Cristhian explica cómo está hecho el sistema y por qué decidió así en cada caso."

## Parte 2. Cómo está hecho y por qué decide (Cristhian Bolaños, 2:40-5:40)

Todo lo de esta parte es público: no necesita la VPN.

**Pestañas, en orden:** el mapa interactivo (https://crissebasbol.github.io/housing-price-mlops/arquitectura.html, zoom al 80 %); el repo en GitHub (vista de archivos); el README en la sección 4, "La decisión de entrenar"; el README en la sección 5, "Compuertas de promoción" (tabla y captura de las compuertas del ingreso 5); el README en la sección 7, captura "Razón del rechazo de la versión 5"; el mapa en el recorrido de GitOps (https://crissebasbol.github.io/housing-price-mlops/arquitectura.html#gitops); GitHub Actions y una corrida de `Build Airflow` o `Build API`; DockerHub (`crissebasbol/housing-api` o `housing-airflow`, pestaña Tags); el commit del bot en GitHub.

**Mostrar y decir:**

1. **(2:40-3:25) La arquitectura completa**, en el mapa:
   - Sin recorrido activo: "Arriba, fuera del clúster: el repositorio en GitHub, la CI en GitHub Actions y las imágenes en DockerHub. Abajo, el clúster RKE2 con dos nodos: `nodo-data` ingiere, valida, entrena y guarda; `nodo-serving` responde predicciones y mide todo. Cada caja es un servicio desplegado por Argo CD." Tocar **PostgreSQL de datos** para mostrar el panel: "RAW guarda cada lote sin modificar, CLEAN las filas válidas y `audit` lo que pasó con cada lote y cada modelo."
   - Botón **Una predicción**: "La predicción que mostró Fabián recorre este camino: Streamlit, la API con el champion en memoria y el registro en PostgreSQL."
   - Botón **Un lote de datos**: "Cada 15 minutos Airflow pide un lote, lo guarda tal cual en MinIO, lo valida, lo pasa a RAW y CLEAN y decide si entrenar. Si entrena, registra el candidato en MLflow y, si pasa las compuertas, mueve el alias `champion`. La API revisa ese alias cada 30 segundos y carga el modelo nuevo sin reiniciarse."
2. **(3:25-3:45) Organización del repositorio**, recorriendo las carpetas en GitHub: "`housing_ml` es el paquete con la lógica del modelo: esquema, calidad, drift, decisión y compuertas; lo usan igual Airflow y la API. `airflow`, `api` y `streamlit` tienen el código y el Dockerfile de cada servicio; `database`, `minio`, `mlflow` y `observability`, sus manifiestos; `argocd`, las apps; `.github/workflows`, la CI. El README es el informe, con la bitácora y la evidencia de cada etapa."
3. **(3:45-4:15) Por qué entrena o no**, en el README, sección 4, "La decisión de entrenar":
   - "No entrena si el esquema es inválido, si se rechazó más del 20 % de las filas o si el lote es pequeño: menos de 10 mil filas o menos del 5 % de lo acumulado. Si no, entrena cuando hay una señal: drift, categorías nuevas, un 20 % más de datos, degradación del modelo en producción o drift en lo que recibe la API."
   - "El ingreso 4 que señaló Fabián trae 4.054 filas, el 1 % de lo acumulado: no entrena. El ingreso 5 trae precios entre 300 y 500 mil dólares, un rango que no se había visto, con un PSI del precio de 8: entrena por drift. La decisión nunca depende de la hora ni de cuántos lotes van, y la razón queda escrita en la auditoría y en MLflow."
4. **(4:15-4:50) Por qué promueve o no**, en la sección 5, "Compuertas de promoción", y en la sección 7:
   - En la tabla: "El candidato y el modelo en producción se comparan sobre el mismo holdout, y el candidato tiene que pasar seis compuertas: mejor error total, una diferencia significativa por bootstrap, no peor en los datos recientes ni en ningún segmento, predicciones sanas y un presupuesto de servicio de 150 milisegundos."
   - En la captura de las compuertas del ingreso 5: "La versión 4 bajó el MAPE de 28,7 a 20,5 % y el intervalo del bootstrap queda por debajo de cero: pasa todas y se promueve."
   - En la captura del rechazo de la versión 5: "La versión 5 era todavía mejor, 20,9 frente a 28,3 %, pero tarda 152 milisegundos por predicción: la compuerta de latencia la rechaza. Queda como challenger y la API la corre en sombra. Promover es mover el alias `champion` en MLflow, no tocar la API."
5. **(4:50-5:40) Del código al clúster y paso a la parte 3.**
   - En el mapa (`#gitops`), dejar que avancen los tres primeros pasos (unos 12 s): "Todo cambio entra por un PR revisado por otro integrante. Al fusionarlo, GitHub Actions construye la imagen y la publica en DockerHub con el SHA del commit."
   - En Actions: "Cada PR corre la CI: ruff, 89 pruebas y la validación de todos los manifiestos con kubeconform." Abrir una corrida de build.
   - En DockerHub, el tag `sha-...`; en GitHub, el commit del bot: "Este commit `Imagen api sha-...` lo hace el workflow: cambia el tag en el manifiesto. Organista muestra cómo Argo CD lleva ese commit al clúster."

## Parte 3. Cómo corre en el clúster y cuánto aguanta (Cristian Organista, 5:40-9:25)

**Pestañas, en orden:** Argo CD (`:8006`, Applications y la app `serving` o `airflow`); terminal en la .106; Airflow (`:8002`), DAG `housing_pipeline` en vista **Graph** y en vista **Grid**; MLflow (`:8003`), experimento `housing-price` (Training runs), el run `c1-b4-...` (Overview y Artifacts) y el menú Models; el mapa en el recorrido de la carga (https://crissebasbol.github.io/housing-price-mlops/arquitectura.html#carga, zoom al 80 %); Grafana, dashboard **Housing API**, con el rango de las pruebas del 23 de noviembre (de 18:45 a 19:50 aproximadamente, o "Last 2 days" y hacer zoom); Locust (`:8010`) o la terminal con el `resumen.csv`.

**Mostrar y decir:**

1. **(5:40-6:10) Argo CD.** Applications: "Aplicamos una sola app a mano, `housing-root`; ella crea las demás desde Git: plataforma de datos, Airflow, serving y observabilidad, todas Synced y Healthy." Abrir **History and Rollback** de `airflow` o `serving`: "Aquí está el commit del bot que mostró Cristhian: el cambio en Git llegó solo al clúster."
2. **(6:10-6:30) Kubernetes.** En la terminal:
   ```bash
   kubectl -n housing-mlops get pods -o wide
   kubectl -n housing-mlops get hpa api
   ```
   "Cada pod en su nodo; todos con requests, limits y probes; las contraseñas en Secrets, nunca en el repo. La API escala de 2 a 3 réplicas por CPU."
3. **(6:30-7:15) El DAG en ejecución.** En la vista Graph: "Una ejecución es una petición a la API de datos, es decir, un lote: 26 tareas de responsabilidad única. Hay tres bifurcaciones: `route_batch` separa un lote nuevo, uno repetido y el fin de datos; `decide_training` elige entre entrenar o no; `decide_promotion`, entre promover o rechazar. Antes de pedir un lote, `check_dependencies` revisa que todo esté arriba." En la vista Grid: "Corre cada 15 minutos desde el 22 de noviembre: aquí se ven las ramas de cada corrida, las que promueven, las que rechazan, las que no entrenan, el fin de datos y los lotes repetidos que solo vigilan al modelo."
4. **(7:15-7:55) MLflow.** La lista de runs: "Un run por entrenamiento, cada uno con su versión registrada." Abrir `c1-b4`: "Cada run guarda el lote, la huella de los datos, el commit de la imagen que entrenó, la razón del entrenamiento y de la promoción, las métricas y artefactos como SHAP." En Models: "Los alias: `champion` en la versión 4, `challenger` en la 5 y `previous_champion` en la 3, para volver atrás si hace falta. La API sirve lo que diga `champion`, y ya veremos cuánto aguanta."
5. **(7:55-8:15) Cómo se hizo la prueba de carga.** En el mapa (`#carga`), el primer paso resalta la flecha de Locust a la API mientras se dice: "Locust corre en el clúster, en otro nodo para no quitarle CPU a la API, con dos tipos de usuario: predicciones normales y filas del holdout con su precio real, para medir el error en línea. Corrimos escalones de 10, 25, 50 y 100 usuarios."
6. **(8:15-9:00) Qué se vio en Grafana**, recorriendo los paneles en el rango de las pruebas:
   - "Con dos réplicas fijas, la API se estancó en unas 8 peticiones por segundo: más usuarios solo alargaban la cola, de 300 milisegundos a 11 segundos de mediana."
   - "En los recursos se ve por qué: la CPU de cada réplica pegada a su límite. Cada predicción cuesta unos 250 milisegundos de CPU."
   - "Agregamos un autoescalado y el HPA subió a tres réplicas: unas 11 peticiones por segundo, un 30 % más, sin fallos ni reinicios."
   - "Y el replay muestra que la sombra, la versión 5, se equivoca menos que el champion también en producción. Es el compromiso entre precisión y costo que hizo que la compuerta de latencia la rechazara."
7. **(9:00-9:25) Cierre.** "En resumen: los datos llegan por lotes, el sistema decide solo cuándo entrenar y qué modelo servir, y todo se despliega desde Git. El detalle, las decisiones, los problemas que encontramos y la evidencia de cada etapa están en el README del repositorio. Gracias."

## Después de grabar

1. Unir las tres partes en orden y revisar que dure menos de 10 minutos.
2. Subir a YouTube como **Público** o **No listado** (que se abra sin iniciar sesión), con el título "Housing Price MLOps: proyecto final MLOps PUJ" y el enlace al repositorio en la descripción.
3. Pasar el enlace a Cristhian. El PR con el enlace en el README va el **jueves 26** y debe ser el último merge del proyecto.
