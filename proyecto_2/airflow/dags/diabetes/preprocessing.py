import hashlib

import pandas as pd

from .config import (
    A1C_VALUES,
    ADMISSION_SOURCE,
    ADMISSION_TYPE,
    AGE_BINS,
    DIABETES_MEDS,
    DISCHARGE_DISPOSITION,
    DISCHARGE_EXCLUDED,
    FEATURES,
    GENDERS,
    GLU_VALUES,
    INTEGER_COLUMNS,
    KEPT_MEDS,
    MED_VALUES,
    RAW_COLUMNS,
    TARGET_MAP,
    TOP_SPECIALTIES,
    TRAIN_PCT,
    VAL_PCT,
)


def row_hash(values: list[str]) -> str:
    """md5 de los valores crudos: identidad de la fila en raw y clean."""
    return hashlib.md5("|".join(values).encode("utf-8")).hexdigest()


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validation_reason(row: pd.Series) -> str | None:
    """Motivo de rechazo de una fila cruda, o None si es valida."""
    for column in RAW_COLUMNS:
        if row[column] == "":
            return f"{column} vacio"

    for column, (low, high) in INTEGER_COLUMNS.items():
        value = _to_int(row[column])
        if value is None:
            return f"{column} no es entero"
        if value < low or (high is not None and value > high):
            return f"{column} fuera de rango"

    checks = {
        "readmitted": TARGET_MAP,
        "gender": GENDERS,
        "age": AGE_BINS,
        "max_glu_serum": GLU_VALUES,
        "a1cresult": A1C_VALUES,
    }
    for column, allowed in checks.items():
        if row[column] not in allowed:
            return f"{column} con valor no permitido: {row[column]}"

    for column in DIABETES_MEDS:
        if row[column] not in MED_VALUES:
            return f"{column} con valor no permitido: {row[column]}"
    return None


def validate_batch(raw: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    """Separa las filas validas de las rechazadas (con su motivo)."""
    reasons = raw.apply(validation_reason, axis=1)
    duplicated = raw["encounter_id"].duplicated(keep="first")
    reasons = reasons.where(~duplicated, "encounter_id duplicado en el lote")

    rejected = {h: r for h, r in zip(raw["row_hash"], reasons) if isinstance(r, str)}
    valid = [h for h in raw["row_hash"] if h not in rejected]
    return valid, rejected


def diag_group(code: str) -> str:
    """Agrupa el codigo ICD-9 en las categorias de Strack et al. (2014)."""
    if code in ("", "?"):
        return "Unknown"
    if code.startswith(("V", "E")):
        return "Other"
    try:
        value = float(code)
    except ValueError:
        return "Other"
    whole = int(value)
    if whole == 250:
        return "Diabetes"
    if 390 <= whole <= 459 or whole == 785:
        return "Circulatory"
    if 460 <= whole <= 519 or whole == 786:
        return "Respiratory"
    if 520 <= whole <= 579 or whole == 787:
        return "Digestive"
    if 580 <= whole <= 629 or whole == 788:
        return "Genitourinary"
    if 710 <= whole <= 739:
        return "Musculoskeletal"
    if 800 <= whole <= 999:
        return "Injury"
    if 140 <= whole <= 239:
        return "Neoplasms"
    return "Other"


def assign_split(patient_nbr: str) -> str:
    """Split estable por paciente: todos los encuentros de un paciente caen en el
    mismo conjunto en cualquier ejecucion, sin fuga entre train y test."""
    bucket = int(hashlib.md5(patient_nbr.encode("utf-8")).hexdigest(), 16) % 100
    if bucket < TRAIN_PCT:
        return "train"
    if bucket < TRAIN_PCT + VAL_PCT:
        return "val"
    return "test"


def clean_batch(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Transforma filas crudas validas en la tabla clean.

    Devuelve el DataFrame limpio y los row_hash excluidos (pacientes fallecidos o
    en hospicio, que no pueden ser readmitidos).
    """
    excluded_mask = raw["discharge_disposition_id"].isin(DISCHARGE_EXCLUDED)
    excluded = raw.loc[excluded_mask, "row_hash"].tolist()
    df = raw.loc[~excluded_mask].copy()

    clean = pd.DataFrame({
        "row_hash": df["row_hash"],
        "batch_id": df["batch_id"],
        "encounter_id": df["encounter_id"].astype("int64"),
        "patient_nbr": df["patient_nbr"].astype("int64"),
        "split": df["patient_nbr"].map(assign_split),
    })

    for column in INTEGER_COLUMNS:
        if column not in ("encounter_id", "patient_nbr"):
            clean[column] = df[column].astype("int64")

    meds = df[DIABETES_MEDS]
    clean["diabetes_meds_active"] = (meds != "No").sum(axis=1)
    clean["diabetes_meds_changed"] = meds.isin(["Up", "Down"]).sum(axis=1)

    clean["age"] = df["age"]
    clean["race"] = df["race"].replace("?", "Unknown")
    clean["gender"] = df["gender"]
    clean["admission_type"] = df["admission_type_id"].map(ADMISSION_TYPE).fillna("Unknown")
    clean["discharge_disposition"] = df["discharge_disposition_id"].map(DISCHARGE_DISPOSITION).fillna("Other")
    clean["admission_source"] = df["admission_source_id"].map(ADMISSION_SOURCE).fillna("Other")
    clean["medical_specialty"] = df["medical_specialty"].where(
        df["medical_specialty"].isin(TOP_SPECIALTIES),
        df["medical_specialty"].map(lambda v: "Unknown" if v == "?" else "Other"),
    )
    for column in ("diag_1", "diag_2", "diag_3"):
        clean[f"{column}_group"] = df[column].map(diag_group)

    for column in ["max_glu_serum", "a1cresult", *KEPT_MEDS, "change", "diabetesmed"]:
        clean[column] = df[column]

    clean["readmitted"] = df["readmitted"]
    clean["target"] = df["readmitted"].map(TARGET_MAP).astype("int64")

    ordered = ["row_hash", "batch_id", "encounter_id", "patient_nbr", "split", *FEATURES, "readmitted", "target"]
    return clean[ordered], excluded
