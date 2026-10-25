# mlflow

- `postgres-mlflow`: backend store (metadatos de experimentos y Model Registry).
- `mlflow`: servidor MLflow 3.16.1 (`crissebasbol/proyecto2-mlflow`) con
  `--artifacts-destination s3://mlflows3/artifacts --serve-artifacts`. Los clientes (Airflow
  y API) suben y descargan artefactos a través del servidor, sin credenciales de MinIO.

Modelo registrado: `diabetes_readmission`, alias `champion` (productivo) y `challenger`
(mejor candidato de la última ejecución).
