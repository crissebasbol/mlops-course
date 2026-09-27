from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

from covertype import tasks
from covertype.config import COLLECT_INTERVAL_SECONDS, TRAINING_DATASET

with DAG(
    dag_id="covertype_data_collection",
    description="Pide un batch a la Data API, lo guarda crudo, lo procesa y lo deja listo para entrenar",
    start_date=datetime(2026, 9, 1),
    schedule=timedelta(seconds=COLLECT_INTERVAL_SECONDS),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)}
) as dag:

    t1 = PythonOperator(
        task_id="t1_resolver_fuente",
        python_callable=tasks.resolver_fuente,
    )

    t2 = PythonOperator(
        task_id="t2_obtener_datos",
        python_callable=tasks.obtener_datos,
    )

    t3 = PythonOperator(
        task_id="t3_preprocesar_datos",
        python_callable=tasks.preprocesar_datos,
    )

    t4 = PythonOperator(
        task_id="t4_preparar_entrenamiento",
        python_callable=tasks.preparar_entrenamiento,
    )

    t5 = ShortCircuitOperator(
        task_id="t5_ciclo_completo",
        python_callable=tasks.ciclo_completo,
    )

    t6 = PythonOperator(
        task_id="t6_publicar_dataset",
        python_callable=tasks.publicar_dataset,
        outlets=[TRAINING_DATASET],
    )

    t1 >> t2 >> t3 >> t4 >> t5 >> t6
