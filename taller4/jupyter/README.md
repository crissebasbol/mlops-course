# JupyterLab

Entorno de JupyterLab donde se hace la experimentación: carga los datos a la
base de datos, los procesa, entrena 24 modelos y los registra en MLflow.

## Servicios

| Servicio  | Contenedor        | Puerto host | Para qué sirve |
|-----------|-------------------|-------------|----------------|
| `jupyter` | `taller4-jupyter` | 8017        | JupyterLab     |

URL: http://10.43.97.92:8017, token `admin123`.

## Notebook `covertype_mlflow.ipynb`

| Sección | Qué hace                                                                                                                                                                                                                        |
|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Datos crudos | Copia el CSV completo a `raw_covertype` con `COPY` (todo `TEXT`). Si la tabla ya tiene las mismas filas que el CSV, no la recarga.                                                                                              |
| 2. Procesamiento | Lee `raw_covertype`, tipa, limpia, quita duplicados, hace split estratificado 80/20 y guarda `clean_covertype`. Solo reprocesa si raw se recargó o si `clean_covertype` no existe o está vacía.                                  |
| 3. Datos de entrenamiento | Lee `clean_covertype` y toma una muestra de `SAMPLE_SIZE` (50.000) filas de train y 12.500 de test.                                                                                                                             |
| 4. Pipeline | `OneHotEncoder` para `wilderness_area` y `soil_type` + `RandomForestClassifier`                                                                                                                                                 |
| 5. Experimentación | Grilla de 3 × 4 × 2 = **24 combinaciones** (`n_estimators`, `max_depth`, `max_features`). Un run padre y un run anidado por combinación con parámetros, métricas y modelo. Cada modelo se registra como versión de `covertype_rf`. |
| 6. Campeón | Ordena por `f1_macro` y pone el alias `champion` a la mejor versión.                                                                                                                                                            |
| 7. Verificación | Carga `models:/covertype_rf@champion` (igual que la API) y predice unas filas de test.                                                                                                                                          |

Con `FORCE_RELOAD = True` (celda de configuración) se recargan y reprocesan los datos siempre, por ejemplo después de cambiar la lógica de procesamiento.