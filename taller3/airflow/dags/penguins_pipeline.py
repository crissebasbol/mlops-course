from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from penguins import tasks

with DAG(
    dag_id="penguins_training_pipeline",
    description="Borra, carga, preprocesa y entrena modelos de Penguins",
    start_date=datetime(2026, 9, 1),
    schedule_interval="@once"
) as dag:

    t1 = PythonOperator(
        task_id="t1_borrar_datos",
        python_callable=tasks.borrar_datos,
    )

    t2 = PythonOperator(
        task_id="t2_cargar_datos_crudos",
        python_callable=tasks.cargar_datos_crudos,
    )

    t3 = PythonOperator(
        task_id="t3_preprocesar_datos",
        python_callable=tasks.preprocesar_datos,
    )

    t4 = PythonOperator(
        task_id="t4_entrenar_modelos",
        python_callable=tasks.entrenar_modelos,
    )

    t1 >> t2 >> t3 >> t4
