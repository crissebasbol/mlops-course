# Taller 1 - Penguin Species Inference API

API REST construida con **FastAPI** que sirve dos modelos entrenados sobre el dataset [Palmer Penguins](https://pypi.org/project/palmerpenguins/) para predecir la especie de un pinguino.

## Modelos disponibles

| Nombre | Archivo | Tipo | Features requeridas |
|--------|---------|------|---------------------|
| `random_forest` | `modelo1/random_forest.pkl` | Clasificador supervisado | 4 numericas + island + sex |
| `gmm` | `modelo 2/penguin_gmm.pkl` | Clustering GMM (no supervisado) | 4 numericas |

## Estructura

```
taller1/
├── main.py            # API FastAPI
├── requirements.txt
├── Dockerfile
├── README.md
├── modelo1/
│   ├── train.py
│   ├── random_forest.pkl
│   └── ...
└── modelo 2/
    ├── train_model.py
    ├── penguin_gmm.pkl
    └── ...
```

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/models` | Lista de modelos disponibles |
| `POST` | `/predict` | Predice la especie |

El campo `model_name` en el body de `/predict` es opcional. Si no se envia, se usa `random_forest` por defecto.

### Documentacion interactiva

Con el servidor corriendo, visita `http://localhost:8989/docs` (Swagger UI).

## Configuracion local

```bash
# Desde la carpeta taller1/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8989
```

## Docker

```bash
# Desde la carpeta taller1/ (contexto de build)
docker build -t penguin-api .
docker run -p 8989:8989 penguin-api
```

## Ejemplos de uso

### Predecir con el modelo por defecto (random_forest)

```bash
curl -X POST http://localhost:8989/predict \
  -H "Content-Type: application/json" \
  -d '{
    "bill_length_mm": 39.1,
    "bill_depth_mm": 18.7,
    "flipper_length_mm": 181.0,
    "body_mass_g": 3750.0,
    "island": "Torgersen",
    "sex": "male"
  }'
# {"species":"Adelie","model_used":"random_forest"}
```

### Predecir especificando el modelo en el request (bono)

```bash
curl -X POST http://localhost:8989/predict \
  -H "Content-Type: application/json" \
  -d '{
    "bill_length_mm": 39.1,
    "bill_depth_mm": 18.7,
    "flipper_length_mm": 181.0,
    "body_mass_g": 3750.0,
    "model_name": "gmm"
  }'
# {"species":"Adelie","model_used":"gmm"}
```

### Consultar modelos disponibles

```bash
curl http://localhost:8989/models
# {"default_model":"random_forest","available":{"random_forest":"Random Forest Classifier (supervisado)","gmm":"Gaussian Mixture Model (no supervisado)"}}
```
