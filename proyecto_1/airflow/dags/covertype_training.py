from datetime import datetime

from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator

from covertype import tasks
from covertype.config import TRAINING_DATASET

# Dos formas de dispararlo:
#   1. Automatica: cuando covertype_data_collection completa los 10 batches
#   2. Manual: boton "Trigger DAG" en la UI.
with DAG(
    dag_id="covertype_model_training",
    description="Entrena rf y gmm con los datos listos para entrenamiento y los versiona en MinIO",
    start_date=datetime(2026, 9, 1),
    schedule=[TRAINING_DATASET],
    catchup=False,
    max_active_runs=1
) as dag:

    decidir = BranchPythonOperator(
        task_id="decidir_entrenamiento",
        python_callable=tasks.decidir_entrenamiento,
    )

    for model_type in ("rf", "gmm"):
        decidir >> PythonOperator(
            task_id=f"entrenar_{model_type}",
            python_callable=tasks.entrenar,
            op_kwargs={"model_type": model_type},
        )
