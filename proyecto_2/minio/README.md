# minio

MinIO como StatefulSet (PVC de 10 Gi, nodo `data`) y el Job `minio-init`, que crea los buckets:

- `mlflows3`: artefactos de MLflow (`s3://mlflows3/artifacts`).
- `datasets`: CSV fuente (`source/Diabetes.csv`), lotes limpios intermedios (`staging/`) y
  los snapshots de train/val/test de cada ejecución del DAG (`splits/<run_id>/`).

Credenciales en el Secret `minio-credentials`; MLflow y Airflow las leen de ahí.
