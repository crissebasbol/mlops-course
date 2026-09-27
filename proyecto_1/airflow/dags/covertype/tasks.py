from dataclasses import asdict

from .config import (
    AUTO_RESTART_COLLECTION,
    CLEAN_TABLE,
    GROUP_NUMBER,
    RAW_TABLE,
    REQUIRED_BATCHES,
    TRAIN_ONLY_IF_NO_MODEL,
    TRAIN_TABLE,
)
from .database import CovertypeDatabase
from .preprocessing import CovertypePreprocessor
from .source_client import CollectionExhausted, DataSource, DataSourceClient


def resolver_fuente() -> dict:
    """consulta el estado del host remoto y decide de donde se leen los datos."""
    fuente = DataSourceClient.resolve()
    print(f"Fuente de datos: {fuente.name} ({fuente.base_url})")
    return asdict(fuente)


def obtener_datos(ti, run_id: str) -> dict:
    """UNA peticion y guarda las filas crudas"""
    fuente = DataSource(**ti.xcom_pull(task_ids="t1_resolver_fuente"))
    cliente = DataSourceClient(fuente)
    db = CovertypeDatabase()
    db.ensure_schema()

    ciclo = db.current_cycle(fuente.name, GROUP_NUMBER)
    base = {"source": fuente.name, "group_number": GROUP_NUMBER, "cycle": ciclo}

    try:
        batch = cliente.fetch_batch()
    except CollectionExhausted as exc:
        print(f"La API ya entrego todos los batches del ciclo {ciclo}: {exc}")
        db.log_request(dag_run_id=run_id, status="exhausted", **base)
        if not AUTO_RESTART_COLLECTION:
            return {**base, "status": "exhausted"}

        cliente.restart()
        new_ciclo = ciclo +1
        db.log_request(dag_run_id=run_id, status="restarted", **{**base, "cycle": new_ciclo})
        print(f"Recoleccion reiniciada, siguiente ciclo: {new_ciclo}")
        return {**base, "status": "restarted", "next_cycle": new_ciclo}

    vistos = db.batches_in_cycle(fuente.name, GROUP_NUMBER, ciclo)
    insertadas = db.insert_raw(
        batch.rows, source=fuente.name, cycle=ciclo, batch_number=batch.batch_number, dag_run_id=run_id
    )
    db.log_request(
        dag_run_id=run_id,
        status="ok",
        batch_number=batch.batch_number,
        rows_received=len(batch.rows),
        rows_inserted=insertadas,
        **base,
    )

    resumen = {
        **base,
        "status": "ok",
        "batch_number": batch.batch_number,
        "is_new_batch": batch.batch_number not in vistos,
        "batches_in_cycle": len(vistos | {batch.batch_number}),
        "rows_received": len(batch.rows),
        "rows_inserted": insertadas,
        "rows_duplicated": len(batch.rows) - insertadas,
        "total_raw": db.count(RAW_TABLE),
    }
    print(f"Batch recibido: {resumen}")
    return resumen


def preprocesar_datos() -> dict:
    """Procesa tabla (tipado y validado)."""
    db = CovertypeDatabase()
    crudo = db.read_unprocessed_raw()
    if crudo.empty:
        print("No hay filas crudas pendientes por procesar")
        return {"filas_crudas": 0, "filas_limpias": 0}

    limpio = CovertypePreprocessor().transform(crudo)
    insertadas = db.write_clean(limpio, crudo["row_hash"].tolist())

    resumen = {
        "filas_crudas": len(crudo),
        "filas_limpias": insertadas,
        "filas_descartadas": len(crudo) - len(limpio),
        "total_limpias": db.count(CLEAN_TABLE),
    }
    print(f"Preprocesamiento: {resumen}")
    return resumen


def preparar_entrenamiento() -> dict:
    """filas procesadas completas a la tabla lista para entrenamiento."""
    db = CovertypeDatabase()
    nuevas = db.promote_to_training()
    resumen = {"filas_nuevas": nuevas, "total_entrenamiento": db.count(TRAIN_TABLE)}
    print(f"Datos listos para entrenamiento: {resumen}")
    return resumen


def ciclo_completo(ti) -> bool:
    """True solo en la ejecucion que completa los 10
    batches del ciclo; en cualquier otra se salta la publicacion del Dataset."""
    datos = ti.xcom_pull(task_ids="t2_obtener_datos") or {}
    completo = (
        datos.get("status") == "ok"
        and datos.get("is_new_batch", False)
        and datos.get("batches_in_cycle") == REQUIRED_BATCHES
    )
    print(
        f"Ciclo {datos.get('cycle')} ({datos.get('source')}): "
        f"{datos.get('batches_in_cycle', 0)}/{REQUIRED_BATCHES} batches -> "
        f"{'completo, se publica el Dataset' if completo else 'aun no'}"
    )
    return completo


def publicar_dataset(ti) -> dict:
    """su `outlet` actualiza el Dataset y eso dispara el DAG de entrenamiento."""
    datos = ti.xcom_pull(task_ids="t2_obtener_datos")
    print(f"Ciclo {datos['cycle']} completo con {REQUIRED_BATCHES} batches, se avisa al DAG de entrenamiento")
    return {"source": datos["source"], "cycle": datos["cycle"]}


def decidir_entrenamiento(dag_run) -> list[str]:
    """que modelos entrenar"""
    from .storage import ModelRegistry
    from .training import TRAINERS

    tipos = list(TRAINERS)
    if dag_run.run_type == "manual" or not TRAIN_ONLY_IF_NO_MODEL:
        elegidos = tipos
    else:
        registry = ModelRegistry()
        elegidos = [t for t in tipos if not registry.has_model(t)]

    print(f"run_type={dag_run.run_type}, TRAIN_ONLY_IF_NO_MODEL={TRAIN_ONLY_IF_NO_MODEL} -> entrenar {elegidos or 'nada'}")
    return [f"entrenar_{t}" for t in elegidos]


def entrenar(model_type: str, run_id: str) -> dict:
    """Entrena un tipo de modelo con la tabla de entrenamiento y lo versiona en MinIO."""
    from .storage import ModelRegistry
    from .training import TRAINERS

    df = CovertypeDatabase().read_training()
    resultado = TRAINERS[model_type]().run(df, ModelRegistry(), dag_run_id=run_id)
    print(f"{model_type}: {resultado}")
    return resultado
