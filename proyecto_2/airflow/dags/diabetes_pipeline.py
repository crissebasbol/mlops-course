from datetime import datetime, timedelta

from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from airflow.sdk import DAG

from diabetes import tasks
from diabetes.config import MODEL_TYPES

with DAG(
    dag_id="diabetes_pipeline",
    description="Carga incremental por lotes, limpieza, entrenamiento, registro y promocion del modelo de readmision",
    start_date=datetime(2026, 10, 1),
    schedule="*/10 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)},
    tags=["proyecto2", "diabetes"],
) as dag:

    t01 = PythonOperator(task_id="t01_validar_fuente", python_callable=tasks.validar_fuente)
    t02 = PythonOperator(task_id="t02_cargar_lote_raw", python_callable=tasks.cargar_lote_raw)
    hay_lote = ShortCircuitOperator(task_id="hay_lote_nuevo", python_callable=tasks.hay_lote_nuevo)
    t03 = PythonOperator(task_id="t03_validar_calidad", python_callable=tasks.validar_calidad)
    t04 = PythonOperator(task_id="t04_preprocesar", python_callable=tasks.preprocesar)
    t05 = PythonOperator(task_id="t05_guardar_clean", python_callable=tasks.guardar_clean)
    t06 = PythonOperator(task_id="t06_split", python_callable=tasks.separar_datos)
    t07 = [
        PythonOperator(
            task_id=f"t07_entrenar_{model_type}",
            python_callable=tasks.entrenar,
            op_kwargs={"model_type": model_type},
        )
        for model_type in MODEL_TYPES
    ]
    t08 = PythonOperator(task_id="t08_registrar_mlflow", python_callable=tasks.registrar_modelos)
    t09 = PythonOperator(task_id="t09_comparar", python_callable=tasks.comparar_modelos)
    t10 = PythonOperator(task_id="t10_promover", python_callable=tasks.promover_modelo)

    t01 >> t02 >> hay_lote >> t03 >> t04 >> t05 >> t06 >> t07 >> t08 >> t09 >> t10
