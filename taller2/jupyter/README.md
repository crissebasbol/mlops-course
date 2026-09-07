# Servicio de Jupyter Notebook

Entorno de Jupyter Notebook dockerizado para construir y entrenar modelos de
machine learning con scikit-learn.

## Propósito

Este proyecto ejecuta un servidor de Jupyter Notebook dentro de Docker. Viene
preconfigurado con las librerías básicas necesarias para crear modelos con
scikit-learn, de modo que el kernel tiene todo listo desde el inicio.

## Herramientas

Las dependencias se gestionan con [`uv`](https://github.com/astral-sh/uv) y se
declaran en `pyproject.toml`. Durante el build de Docker, `uv` instala esas
dependencias en el entorno del notebook.

Librerías preinstaladas:

- `matplotlib`
- `numpy`
- `seaborn`
- `scikit-learn`
- `scipy`

## Notebook

En el almacenamiento compartido hay un notebook listo para usar:
`../shared_storage/train_models.ipynb`. Entrena dos tipos de modelos sobre el
dataset de pingüinos:

- **GMM** (`GaussianMixture`): pipeline de clustering no supervisado.
- **RF** (`RandomForest`, entre otros clasificadores): pipeline de
  clasificación supervisada.

## Versionado de modelos

Cada modelo nuevo que se guarda se almacena en el almacenamiento compartido en
`../shared_storage/models/`, versionado automáticamente:

- Modelos GMM -> `shared_storage/models/gmm/vN.pkl`
- Modelos RF  -> `shared_storage/models/rf/vN.pkl`

La lógica de guardado busca el último `vN.pkl` en la carpeta destino y crea el
siguiente `v(N+1).pkl`, por lo que las versiones anteriores nunca se
sobrescriben.

## Uso

```bash
cd taller2/jupyter
docker compose up --build
```

Luego abre http://localhost:8888. La carpeta `shared_storage/` se monta dentro
del contenedor en `/home/jovyan/work`, así que los notebooks y los modelos
guardados persisten en el host.
