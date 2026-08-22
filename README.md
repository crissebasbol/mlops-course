# mlops-course

Repositorio de entregables de la materia **MLOps** de la Pontificia Universidad Javeriana.

Cada taller vive en su propia carpeta con su README, requirements y entorno virtual independiente.

## Estructura

```
mlops-course/
└── taller1/           # Taller 1: pipeline ML nivel 0 + API de inferencia
    ├── README.md
    ├── requirements.txt
    ├── main.py            # API FastAPI (puerto 8989)
    ├── Dockerfile
    ├── modelo1/           # Random Forest Classifier
    └── modelo 2/          # Gaussian Mixture Model
```

## Talleres

| Carpeta | Descripción |
|---------|-------------|
| [`taller1/`](taller1/README.md) | Pipeline ML sobre Palmer Penguins + API REST con FastAPI |
