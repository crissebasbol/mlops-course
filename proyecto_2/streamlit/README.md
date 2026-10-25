# streamlit

Interfaz gráfica (`crissebasbol/proyecto2-streamlit`). Solo conoce `API_URL`; no habla con
MLflow ni con la base de datos.

- Formulario con las features de la capa clean, agrupado por secciones.
- Botones de valores de ejemplo por clase (`examples.json`, registros reales del dataset).
- Muestra la clase, la probabilidad, las probabilidades de las 3 clases, la versión del modelo
  y la latencia.
- Pestaña **JSON libre** para enviar cualquier payload y ver los errores de validación (422)
  que devuelve la API.
- Barra lateral con el modelo en producción (`/model-info`).
