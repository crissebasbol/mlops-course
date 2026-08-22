# Mlops — Clustering de Pingüinos

Creacion del modelo de agrupamiento (clustering) no supervisado sobre el dataset de pingüinos (Palmer Penguins), usando **Gaussian Mixture Model (GMM)**. El modelo entrenado se guarda como pipeline (imputación + escalado + GMM) en un archivo `.pkl`.

## Estructura del proyecto

```
Mlops/
├── penguins.csv          # Dataset de entrada
├── train_model.py        # Script de entrenamiento
└── penguin_gmm.pkl       # Modelo entrenado (pipeline serializado)
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

Dependencias (ver `requirements.txt`):

```
scikit-learn==1.9.0
pandas==3.0.5
numpy==2.5.2
joblib==1.5.3
```

Para instalarlas:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Entrenamiento

Ejecutar el script de entrenamiento:

```bash
.venv\Scripts\python.exe train_model.py
```

Esto:
1. Carga `penguins.csv` y limpia filas con valores nulos en las variables numéricas.
2. Construye un pipeline: `SimpleImputer` → `StandardScaler` → `GaussianMixture(n_components=3)`.
3. Entrena el modelo y calcula métricas:
   - **Silhouette score**: qué tan bien separados están los clústeres.
   - **Adjusted Rand Index (ARI)**: qué tanto coinciden los clústeres con la especie real.
   - **Mapeo cluster → especie**: a cada cluster se le asigna el nombre de la especie mayoritaria dentro de él.
   - **Accuracy**: qué tan seguido el nombre de especie asignado coincide con la especie real.
4. Guarda un diccionario `{"pipeline": ..., "cluster_to_species": ...}` en `penguin_gmm.pkl` con `joblib`.

### Resultados actuales

- Muestras usadas: 342
- Silhouette score: ~0.145
- ARI vs especie real: ~0.960
- Mapeo cluster → especie: `{0: 'Adelie', 1: 'Gentoo', 2: 'Chinstrap'}`
- Accuracy (especie por cluster mayoritario): ~0.985

## Uso del modelo entrenado

El `.pkl` contiene el pipeline de GMM junto con el mapeo de cluster a nombre de especie, para predecir directamente el nombre en vez del número de cluster:

```python
import joblib

data = joblib.load("penguin_gmm.pkl")
pipeline = data["pipeline"]
cluster_to_species = data["cluster_to_species"]

# [bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g]
clusters = pipeline.predict([[39.1, 18.7, 181, 3750]])
especies = [cluster_to_species[c] for c in clusters]
print(especies)  # ['Adelie']
```

## Notas

- Se eligió **Gaussian Mixture Model (GMM)** con `n_components=3` (una por cada especie: Adelie, Chinstrap, Gentoo) en lugar de K-Means: al modelar cada cluster como una gaussiana con su propia forma/orientación (en vez de asumir clústeres esféricos como K-Means), captura mejor la superposición entre especies y mejora el ARI (~0.96 vs ~0.79) y la accuracy (~0.985 vs ~0.915).
- El pipeline serializado incluye el imputador y el escalador, por lo que puede recibir datos crudos sin preprocesar previamente.
- Como GMM es no supervisado, los números de cluster no corresponden directamente a una especie; por eso se guarda el mapeo `cluster_to_species` calculado con las etiquetas reales del entrenamiento.
