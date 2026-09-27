# API de inferencia (Covertype)

API REST con FastAPI que sirve los modelos entrenados por el DAG
`covertype_model_training` y guardados de forma versionada en **MinIO**, para
predecir el tipo de cobertura forestal.

## Modelos

- **rf**: Random Forest supervisado. Usa las 10 variables numéricas más
  `wilderness_area` y `soil_type` (one-hot). Un `soil_type` que no apareció en
  el entrenamiento no rompe la predicción.
- **gmm**: Gaussian Mixture no supervisado con 7 componentes sobre las
  variables numéricas; cada cluster se mapea al `cover_type` mayoritario.

Los modelos se leen del bucket `models` (`<tipo>/v<N>/model.pkl`). Solo cuentan
las versiones que ya tienen su `metadata.json`. Cada versión descargada se
guarda en memoria (las últimas `MODEL_CACHE_SIZE`, 4 por defecto), porque una
versión nunca cambia.

## Selección de modelo y versión

- `model_type`: `rf` (por defecto) o `gmm`.
- `version`: opcional; sin ella se usa la **última**. Si no existe, responde
  **404** con las versiones disponibles.

## Endpoints

| Método | Ruta                              | Descripción                                                  |
|--------|-----------------------------------|--------------------------------------------------------------|
| GET    | `/health`                         | Estado del servicio y conexión con MinIO.                    |
| GET    | `/models`                         | Versiones disponibles por tipo y la última.                  |
| GET    | `/models/{model_type}`            | Metadata de todas las versiones de un tipo (métricas, filas, fecha). |
| GET    | `/models/{model_type}/{version}`  | Metadata de una versión.                                     |
| POST   | `/predict`                        | Predice el `cover_type` con el modelo y la versión indicados. |