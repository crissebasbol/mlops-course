# Servicio de API de inferencia (Penguins)

API REST construida con FastAPI que sirve los modelos entrenados por el DAG
de Airflow (`../airflow/dags/penguins/training.py`) para predecir la especie de
un pingüino.

## Qué hace

Expone los modelos guardados de forma versionada por Airflow y permite hacer
inferencia sobre ellos:

- **rf**: Random Forest (y otros clasificadores supervisados). Predice la
  especie a partir de las medidas del pingüino más `island` y `sex`.
- **gmm**: Gaussian Mixture (clustering no supervisado). Asigna un cluster y lo
  mapea a la especie mayoritaria.

Los modelos se leen desde `MODELS_DIR` (por defecto `/models`), que es el
volumen `models-volume` que escribe Airflow, con la estructura `rf/vN.pkl` y
`gmm/vN.pkl`. El API lo monta en modo solo lectura.

## Selección de modelo y versión

Cada petición de inferencia indica el **tipo de modelo** (`rf` o `gmm`) y,
opcionalmente, la **versión**:

- Si no se envía la versión, se usa la **última** disponible.
- Si la versión solicitada no existe, la API responde **404** con un mensaje
  específico indicando las versiones disponibles.

Los modelos se cargan desde disco una sola vez y se cachean en memoria por
`(tipo, versión)` para no releer el `.pkl` en cada petición.

## Endpoints

| Método | Ruta       | Descripción                                                  |
|--------|------------|--------------------------------------------------------------|
| GET    | `/health`  | Estado del servicio y tipo de modelo por defecto.            |
| GET    | `/models`  | Modelos disponibles agrupados por tipo (`rf`, `gmm`) con sus versiones y la última. |
| POST   | `/predict` | Predice la especie según el modelo y versión indicados.      |

### Ejemplo de `/predict`

```bash
# Desde la red: http://10.43.97.92:8024/predict
curl -X POST http://localhost:8024/predict \
  -H "Content-Type: application/json" \
  -d '{
    "bill_length_mm": 39.1,
    "bill_depth_mm": 18.7,
    "flipper_length_mm": 181.0,
    "body_mass_g": 3750.0,
    "island": "Torgersen",
    "sex": "male",
    "model_type": "rf",
    "version": 1
  }'
```

Respuesta:

```json
{ "species": "Adelie", "model_type": "rf", "version": 1 }
```

> Nota: `island` y `sex` son obligatorios para `rf`. Para `gmm` solo se
> requieren las cuatro medidas numéricas. Si se omite `version`, se usa la
> última disponible.

## Herramientas

Las dependencias se gestionan con [`uv`](https://github.com/astral-sh/uv) y se
declaran en `pyproject.toml` (FastAPI, Uvicorn, joblib, NumPy, scikit-learn).
scikit-learn es necesaria para deserializar y ejecutar los modelos, ya que los
`.pkl` contienen objetos de scikit-learn. Sus versiones estan fijadas a las
mismas que usa la imagen de Airflow (`../airflow/requirements.txt`) para que
los `.pkl` carguen sin advertencias de compatibilidad.

## Uso

Desde `taller3/` (levanta el API junto con Airflow y las dos bases de datos):

```bash
docker compose up -d --build
```

El API queda disponible en http://localhost:8024 y su documentación
interactiva en http://localhost:8024/docs.

Desde la red se llega al mismo servicio en http://10.43.97.92:8024 y
http://10.43.97.92:8024/docs: el puerto es el que publica el
`docker-compose.yml`, lo unico que cambia es el host.

> Los modelos los produce el DAG `penguins_training_pipeline`. Hasta que no se
> ejecute al menos una vez, `/predict` responde `404`.
