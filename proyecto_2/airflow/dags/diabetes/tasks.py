import logging
import math
import re

from .config import (
    BATCH_SIZE,
    MAX_REJECTED_PCT,
    MODEL_TYPES,
    RAW_COLUMNS,
    SOURCE_COLUMNS,
    SOURCE_FILE,
    SOURCE_OBJECT,
    SOURCE_URL,
    SPLITS_PREFIX,
    sql_name,
)
from .database import DiabetesDatabase
from .preprocessing import clean_batch, row_hash, validate_batch
from .storage import DatasetStorage

log = logging.getLogger(__name__)

TRAINING_TASKS = [f"t07_entrenar_{m}" for m in MODEL_TYPES]


def _safe(run_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)


def validar_fuente(**_):
    """t01: tablas creadas y archivo fuente disponible en MinIO (se descarga la primera vez)."""
    missing = DiabetesDatabase().missing_tables()
    if missing:
        raise RuntimeError(f"Faltan tablas en la base de datos: {missing}. Revise database/init.")

    storage = DatasetStorage()
    if not storage.exists(SOURCE_OBJECT):
        log.info("Descargando %s desde %s", SOURCE_FILE, SOURCE_URL)
        storage.download_source(SOURCE_URL, SOURCE_OBJECT)

    df = storage.read_csv(SOURCE_OBJECT)
    if list(df.columns) != SOURCE_COLUMNS:
        raise ValueError(f"Columnas inesperadas en {SOURCE_OBJECT}: {list(df.columns)}")
    if df.empty:
        raise ValueError(f"{SOURCE_OBJECT} no tiene filas")

    total_batches = math.ceil(len(df) / BATCH_SIZE)
    log.info("Fuente con %d filas, %d lotes de %d", len(df), total_batches, BATCH_SIZE)
    return {"rows": len(df), "total_batches": total_batches}


def cargar_lote_raw(ti, run_id, **_):
    """t02: inserta el siguiente lote (<= BATCH_SIZE filas) en raw.diabetes."""
    source = ti.xcom_pull(task_ids="t01_validar_fuente")
    db = DiabetesDatabase()
    batch_id = db.next_batch(source["total_batches"])
    if batch_id is None:
        log.info("Todos los lotes ya fueron procesados; no hay datos nuevos")
        return None

    row_start = batch_id * BATCH_SIZE
    row_end = min(row_start + BATCH_SIZE, source["rows"])
    db.start_batch(batch_id, row_start, row_end, SOURCE_FILE, run_id)

    df = DatasetStorage().read_csv(SOURCE_OBJECT).iloc[row_start:row_end].copy()
    df.columns = [sql_name(c) for c in df.columns]
    df["row_hash"] = [row_hash(list(values)) for values in df[RAW_COLUMNS].itertuples(index=False, name=None)]
    df["source_row"] = df.index + 2

    rows = db.insert_raw(df, batch_id, SOURCE_FILE)
    db.update_batch(batch_id, rows_in_file=len(df), rows_inserted=rows, status="loaded")
    log.info("Lote %d: filas %d-%d, %d en raw", batch_id, row_start, row_end, rows)
    return {"batch_id": batch_id, "rows": len(df)}


def hay_lote_nuevo(ti, **_):
    return ti.xcom_pull(task_ids="t02_cargar_lote_raw") is not None


def validar_calidad(ti, **_):
    """t03: valida cada fila del lote y marca status valid/rejected.
    Si el porcentaje rechazado supera MAX_REJECTED_PCT la tarea falla."""
    batch_id = ti.xcom_pull(task_ids="t02_cargar_lote_raw")["batch_id"]
    db = DiabetesDatabase()
    raw = db.fetch_raw(batch_id, ("loaded", "valid", "rejected", "excluded", "processed"))

    valid, rejected = validate_batch(raw)
    db.set_raw_status({h: ("valid", None) for h in valid} | {h: ("rejected", r) for h, r in rejected.items()})

    pct = 100 * len(rejected) / max(len(raw), 1)
    db.update_batch(batch_id, rows_valid=len(valid), rows_rejected=len(rejected), status="validated")
    log.info("Lote %d: %d validas, %d rechazadas (%.2f%%)", batch_id, len(valid), len(rejected), pct)
    if pct > MAX_REJECTED_PCT:
        db.update_batch(batch_id, status="failed")
        raise ValueError(f"Lote {batch_id}: {pct:.2f}% de filas rechazadas (maximo {MAX_REJECTED_PCT}%)")
    return {"batch_id": batch_id, "valid": len(valid), "rejected": len(rejected)}


def preprocesar(ti, **_):
    """t04: limpieza y feature engineering del lote; deja el resultado en MinIO."""
    batch_id = ti.xcom_pull(task_ids="t02_cargar_lote_raw")["batch_id"]
    raw = DiabetesDatabase().fetch_raw(batch_id, ("valid",))
    clean, excluded = clean_batch(raw)

    staging = f"staging/batch_{batch_id}.parquet"
    DatasetStorage().put_parquet(clean, staging)
    log.info("Lote %d: %d filas limpias, %d excluidas", batch_id, len(clean), len(excluded))
    return {"batch_id": batch_id, "staging": staging, "excluded": excluded}


def guardar_clean(ti, **_):
    """t05: upsert en clean.diabetes y cierre del lote (status processed)."""
    info = ti.xcom_pull(task_ids="t04_preprocesar")
    clean = DatasetStorage().get_parquet(info["staging"])
    db = DiabetesDatabase()

    rows = db.upsert_clean(clean)
    statuses = {h: ("processed", None) for h in clean["row_hash"]}
    statuses |= {h: ("excluded", "fallecido u hospicio") for h in info["excluded"]}
    db.set_raw_status(statuses)
    db.update_batch(info["batch_id"], rows_clean=rows, status="processed")
    return {"batch_id": info["batch_id"], "rows_clean": rows}


def separar_datos(ti, run_id, **_):
    """t06: snapshot de train/val/test con todo lo acumulado en clean."""
    from .training import summary

    batch_id = ti.xcom_pull(task_ids="t02_cargar_lote_raw")["batch_id"]
    clean = DiabetesDatabase().fetch_clean()
    prefix = f"{SPLITS_PREFIX}/{_safe(run_id)}"
    storage = DatasetStorage()
    for split in ("train", "val", "test"):
        part = clean[clean["split"] == split]
        if part["target"].nunique() < 3:
            raise ValueError(f"El split {split} no tiene las 3 clases ({len(part)} filas)")
        storage.put_parquet(part, f"{prefix}/{split}.parquet")

    stats = summary(clean)
    log.info("Splits en %s: %s", prefix, stats)
    return {"batch_id": batch_id, "prefix": prefix, "rows": len(clean), "summary": stats}


def entrenar(model_type: str, ti, run_id, **_):
    """t07: entrena un candidato y lo registra como run en MLflow."""
    from .training import train_and_log

    splits = ti.xcom_pull(task_ids="t06_split")
    storage = DatasetStorage()
    data = {s: storage.get_parquet(f"{splits['prefix']}/{s}.parquet") for s in ("train", "val", "test")}
    tags = {"batch_id": str(splits["batch_id"]), "dag_run_id": run_id, "clean_rows": str(splits["rows"])}
    result = train_and_log(model_type, data["train"], data["val"], data["test"], tags)
    log.info("%s: %s", model_type, result)
    return result


def registrar_modelos(ti, **_):
    """t08: registra los candidatos como versiones del modelo en el Model Registry."""
    from .registry import register_candidates

    candidates = ti.xcom_pull(task_ids=TRAINING_TASKS)
    batch_id = ti.xcom_pull(task_ids="t06_split")["batch_id"]
    return register_candidates(list(candidates), batch_id)


def comparar_modelos(ti, **_):
    """t09: compara el mejor candidato contra el champion vigente."""
    from .registry import compare

    registered = ti.xcom_pull(task_ids="t08_registrar_mlflow")
    splits = ti.xcom_pull(task_ids="t06_split")
    val = DatasetStorage().get_parquet(f"{splits['prefix']}/val.parquet")
    decision = compare(registered, val)
    log.info("Decision: %s", decision)
    return decision


def promover_modelo(ti, **_):
    """t10: asigna los alias challenger y, si mejora, champion."""
    from .registry import promote

    result = promote(ti.xcom_pull(task_ids="t09_comparar"))
    log.info("Resultado de la promocion: %s", result)
    return result
