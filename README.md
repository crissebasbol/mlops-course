# Mlops — Clustering de Pingüinos

Creacion del modelo de agrupamiento (clustering) no supervisado sobre el dataset de pingüinos (Palmer Penguins), usando **K-Means**. El modelo entrenado se guarda como pipeline (imputación + escalado + K-Means) en un archivo `.pkl`.

## Estructura del proyecto

```
Mlops/
├── penguins.csv          # Dataset de entrada
├── train_model.py        # Script de entrenamiento
└── penguin_kmeans.pkl    # Modelo entrenado (pipeline serializado)
```

## Dataset

`penguins.csv` contiene las siguientes columnas:

| Columna              | Descripción                          |
|-----------------------|---------------------------------------|
| `species`             | Especie del pingüino (Adelie, Chinstrap, Gentoo) |
| `island`               | Isla donde fue observado              |
| `bill_length_mm`       | Longitud del pico (mm)                |
| `bill_depth_mm`        | Profundidad del pico (mm)             |
| `flipper_length_mm`    | Longitud de la aleta (mm)             |
| `body_mass_g`          | Masa corporal (g)                     |
| `sex`                  | Sexo del pingüino                     |

El script solo utiliza las 4 columnas numéricas para el clustering; las filas con valores nulos en esas columnas se descartan.

## Requisitos

- Python 3.13
- Entorno virtual del proyecto: `.venv` (ya configurado como intérprete en PyCharm)

Dependencias (instaladas en `.venv`):

```
scikit-learn
pandas
numpy
joblib
```

Para instalarlas manualmente si hace falta:

```bash
.venv\Scripts\python.exe -m pip install scikit-learn pandas numpy joblib
```

## Entrenamiento

Ejecutar el script de entrenamiento:

```bash
.venv\Scripts\python.exe train_model.py
```

Esto:
1. Carga `penguins.csv` y limpia filas con valores nulos en las variables numéricas.
2. Construye un pipeline: `SimpleImputer` → `StandardScaler` → `KMeans(n_clusters=3)`.
3. Entrena el modelo y calcula métricas:
   - **Silhouette score**: qué tan bien separados están los clústeres.
   - **Adjusted Rand Index (ARI)**: qué tanto coinciden los clústeres con la especie real.
   - **Mapeo cluster → especie**: a cada cluster se le asigna el nombre de la especie mayoritaria dentro de él.
   - **Accuracy**: qué tan seguido el nombre de especie asignado coincide con la especie real.
4. Guarda un diccionario `{"pipeline": ..., "cluster_to_species": ...}` en `penguin_kmeans.pkl` con `joblib`.

### Resultados actuales

- Muestras usadas: 342
- Silhouette score: ~0.199
- ARI vs especie real: ~0.793
- Mapeo cluster → especie: `{0: 'Chinstrap', 1: 'Gentoo', 2: 'Adelie'}`
- Accuracy (especie por cluster mayoritario): ~0.915

## Uso del modelo entrenado

El `.pkl` contiene el pipeline de K-Means junto con el mapeo de cluster a nombre de especie, para predecir directamente el nombre en vez del número de cluster:

```python
import joblib

data = joblib.load("penguin_kmeans.pkl")
pipeline = data["pipeline"]
cluster_to_species = data["cluster_to_species"]

# [bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g]
clusters = pipeline.predict([[39.1, 18.7, 181, 3750]])
especies = [cluster_to_species[c] for c in clusters]
print(especies)  # ['Adelie']
```

## Notas

- Se eligió **K-Means** con `n_clusters=3` (una por cada especie: Adelie, Chinstrap, Gentoo) como alternativa a Gaussian Mixture Models (GMM).
- El pipeline serializado incluye el imputador y el escalador, por lo que puede recibir datos crudos sin preprocesar previamente.
- Como K-Means es no supervisado, los números de cluster no corresponden directamente a una especie; por eso se guarda el mapeo `cluster_to_species` calculado con las etiquetas reales del entrenamiento.
