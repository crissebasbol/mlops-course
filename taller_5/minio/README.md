# MinIO

Almacenamiento S3 donde MLflow guarda los artefactos de los modelos (bucket
`mlflows3`, carpeta `artifacts`).

## Servicios

| Servicio     | Contenedor           | Puerto host | Para qué sirve                              |
|--------------|----------------------|-------------|---------------------------------------------|
| `minio`      | `taller5-minio`      | 8005        | Consola web. La API S3 (9000) solo es interna. |
| `minio-init` | `taller5-minio-init` | -           | Crea el bucket `mlflows3` y termina.        |

Consola: http://10.43.97.105:8005 (`admin` / `admin123`)