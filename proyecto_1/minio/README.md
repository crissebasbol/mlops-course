# MinIO

Almacenamiento de objetos (compatible con S3) donde quedan los modelos
entrenados por Airflow y de donde los lee la API de inferencia.

## Servicios

| Servicio     | Contenedor             | Puerto host         | Para qué sirve                          |
|--------------|------------------------|---------------------|-----------------------------------------|
| `minio`      | `proyecto1-minio`      | 8013 (API), 8014 (consola) | Servidor de objetos             |
| `minio-init` | `proyecto1-minio-init` | -                   | Crea el bucket `models` y termina       |

Consola web: http://10.43.97.92:8014, usuario `admin`, clave `admin123`.

La imagen está fijada a `RELEASE.2025-04-22T22-12-26Z`: que cuenta con la consola web.

## Organización de los modelos

Cada entrenamiento crea una carpeta de versión nueva, con número creciente:

```
models/
├── rf/
│   ├── v1/
│   │   ├── model.pkl        # payload joblib: pipeline de scikit-learn + features
│   │   └── metadata.json    # métricas, filas de train/test, fecha, dag_run_id
│   └── v2/ ...
└── gmm/
    └── v1/ ...
```