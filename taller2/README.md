# Taller 2 - Entrenamiento e inferencia de modelos (Penguins)

Proyecto de MLOps que integra dos servicios en Docker para entrenar modelos de
machine learning y servirlos mediante una API de inferencia, usando un
almacenamiento compartido para versionar los modelos.

## Arquitectura

```
taller2/
├── docker-compose.yml        # Orquesta jupyter + api
├── jupyter/                  # Servicio de Jupyter Notebook (entrenamiento)
├── api/                      # Servicio de API FastAPI (inferencia)
└── shared_storage/           # Volumen compartido entre ambos servicios
    ├── penguins.csv          # Dataset
    ├── train_models.ipynb    # Notebook de entrenamiento
    └── models/               # Modelos versionados
        ├── rf/vN.pkl
        └── gmm/vN.pkl
```

- **jupyter**: entorno con las librerías listas para entrenar modelos con
  scikit-learn. El notebook guarda los modelos de forma versionada en
  `shared_storage/models/`.
- **api**: expone los modelos entrenados vía HTTP para hacer predicciones,
  seleccionando el tipo de modelo (`rf` o `gmm`) y la versión.
- **shared_storage**: carpeta montada en ambos contenedores. Es el punto de
  contacto: Jupyter escribe los modelos y la API los lee.

Para más detalle de cada servicio ver [`jupyter/README.md`](jupyter/README.md)
y [`api/README.md`](api/README.md).

## Cómo correrlo

Desde la carpeta `taller2/`:

```bash
docker compose up --build
```

Servicios disponibles:

| Servicio | URL                          | Descripción                        |
|----------|------------------------------|------------------------------------|
| Jupyter  | http://localhost:8888        | Notebook de entrenamiento          |
| API      | http://localhost:8989        | Inferencia                         |
| API docs | http://localhost:8989/docs   | Documentación interactiva (Swagger)|

Para detenerlo:

```bash
docker compose down
```

## Flujo de uso

### 1. Entrenar los modelos (Jupyter)

1. Abre http://localhost:8888.
2. Abre `train_models.ipynb`.
3. Ejecuta todas las celdas. Esto entrena los modelos **RF** y **GMM** y guarda
   una nueva versión en `shared_storage/models/rf/` y `shared_storage/models/gmm/`.

Cada ejecución de `save_model` crea automáticamente la siguiente versión
(`v1.pkl`, `v2.pkl`, ...), sin sobrescribir las anteriores.

### 2. Probar la API

Una vez existan modelos entrenados, la API los detecta automáticamente (lee el
volumen compartido).

Listar modelos y versiones disponibles:

```bash
curl http://localhost:8989/models
```

Predecir con Random Forest (usa la última versión si se omite `version`):

```bash
curl -X POST http://localhost:8989/predict \
  -H "Content-Type: application/json" \
  -d '{
    "bill_length_mm": 39.1,
    "bill_depth_mm": 18.7,
    "flipper_length_mm": 181.0,
    "body_mass_g": 3750.0,
    "island": "Torgersen",
    "sex": "male",
    "model_type": "rf"
  }'
```

Predecir con GMM y una versión específica:

```bash
curl -X POST http://localhost:8989/predict \
  -H "Content-Type: application/json" \
  -d '{
    "bill_length_mm": 46.5,
    "bill_depth_mm": 17.9,
    "flipper_length_mm": 192.0,
    "body_mass_g": 3500.0,
    "model_type": "gmm",
    "version": 1
  }'
```

Respuesta esperada:

```json
{ "species": "Adelie", "model_type": "rf", "version": 1 }
```

Si se pide una versión que no existe, la API responde **404** indicando las
versiones disponibles.

## Notas

- `island` y `sex` son obligatorios para `rf`; para `gmm` solo las cuatro
  medidas numéricas.
- Si entrenas un modelo nuevo en Jupyter mientras la API está corriendo, la
  nueva versión queda disponible sin reiniciar el contenedor.
