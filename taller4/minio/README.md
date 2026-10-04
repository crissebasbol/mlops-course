# MinIO (artefactos de MLflow)

Almacenamiento de objetos compatible con S3, dedicado a MLflow: ahí quedan los
artefactos de cada run (modelos, firmas, ejemplos de entrada). La configuración
es la misma que usamos en `proyecto_1/minio`, pero es otra instancia, con otros
puertos y otro volumen.

## Servicios

| Servicio     | Contenedor           | Puerto host                | Para qué sirve                    |
|--------------|----------------------|----------------------------|-----------------------------------|
| `minio`      | `taller4-minio`      | 8019 (API), 8020 (consola) | Servidor de objetos               |
| `minio-init` | `taller4-minio-init` | -                          | Crea el bucket `mlflows3` y termina |

Consola web: http://10.43.97.92:8020, usuario `admin`, clave `admin123`.

La imagen es `coollabsio/minio:RELEASE.2025-04-22T22-12-26Z`, la misma de
`proyecto_1` (MinIO dejó de publicar imágenes oficiales; coollabsio las compila
desde el código fuente y es la última versión con la consola completa).

El bucket se llama `mlflows3`. A diferencia de
`proyecto_1` no se activa el versionado del bucket: MLflow ya versiona los
modelos en su Model Registry y cada run escribe en su propia carpeta.

## Organización

MLflow escribe con esta estructura:

```
mlflows3/
└── artifacts/
    └── <experiment_id>/
        └── models/
            └── m-<model_id>/
                └── artifacts/
                    ├── MLmodel
                    ├── model.pkl
                    ├── conda.yaml / python_env.yaml / requirements.txt
                    └── input_example.json
```