# airflow

Airflow 3.1.8 desplegado con el Helm chart, con
`LocalExecutor` y una imagen propia que trae el DAG y las dependencias.

| Archivo | Contenido |
|---|---|
| `Dockerfile`, `requirements.txt` | Imagen `crissebasbol/proyecto2-airflow` |
| `values.yaml` | Valores de Helm: imagen, recursos, `nodeSelector`, variables y Secrets |
| `k8s/` | `postgres-airflow` (metadatos), Secret `airflow-metadata`, ConfigMap `airflow-pipeline` |
| `dags/diabetes_pipeline.py` | DAG principal |
| `dags/diabetes/` | `config`, `database`, `storage`, `preprocessing`, `training`, `registry`, `tasks` |

Los metadatos van en `postgres-airflow` en vez del subchart de Postgres, para controlar
versión, recursos y volumen igual que las otras bases.

```bash
helm upgrade --install airflow apache-airflow/airflow --version 1.22.0 -n proyecto2 -f airflow/values.yaml --wait --timeout 20m
kubectl -n proyecto2 logs statefulset/airflow-scheduler -c scheduler -f
```

Para publicar un cambio del DAG: reconstruir con un tag nuevo
(`./scripts/build_push.sh 1.0.1 airflow`), actualizar `images.airflow.tag` en `values.yaml`
y repetir el `helm upgrade`.
