from dataclasses import asdict, dataclass, field

from housing_ml.formatting import decimal, integer, percent

SIGNAL_CATEGORY_COLUMNS = ("status", "state")


@dataclass(frozen=True)
class TrainingThresholds:
    min_valid_rows: int = 10_000
    min_share_of_accumulated: float = 0.05
    max_rejected_share: float = 0.20
    psi: float = 0.2
    new_category_share: float = 0.02
    volume_growth: float = 0.20
    degradation_factor: float = 1.10
    inference_psi: float = 0.2
    min_inference_events: int = 500


@dataclass
class BatchSignals:
    schema_status: str
    valid_rows: int
    rejected_rows: int
    accumulated_valid_rows: int
    rows_at_last_training: int | None
    has_champion: bool
    drift_psi: dict[str, float | None] = field(default_factory=dict)
    new_category_share: dict[str, float] = field(default_factory=dict)
    champion_mape_on_batch: float | None = None
    champion_reference_mape: float | None = None
    inference_psi: dict[str, float | None] = field(default_factory=dict)
    inference_events: int = 0


@dataclass
class TrainingDecision:
    train: bool
    code: str
    signals: list[str]
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _skip(code: str, reason: str) -> TrainingDecision:
    return TrainingDecision(False, code, [], reason)


def _new_categories_note(signals: BatchSignals) -> str:
    present = {c: s for c, s in signals.new_category_share.items() if s > 0}
    if not present:
        return ""
    listed = ", ".join(f"{c} ({percent(s)} del lote)" for c, s in present.items())
    return (
        f" Trae categorías nuevas en {listed}; sus filas quedan en CLEAN para el próximo "
        "entrenamiento."
    )


def decide_training(
    signals: BatchSignals, thresholds: TrainingThresholds | None = None
) -> TrainingDecision:
    t = thresholds or TrainingThresholds()
    total = signals.valid_rows + signals.rejected_rows
    if signals.schema_status == "invalid":
        return _skip(
            "invalid_schema",
            "No entrena: el esquema del lote es inválido (faltan columnas requeridas o sus "
            "valores no se pueden convertir).",
        )
    if total == 0:
        return _skip("empty", "No entrena: el lote llegó vacío.")

    rejected_share = signals.rejected_rows / total
    if rejected_share > t.max_rejected_share:
        return _skip(
            "low_quality",
            f"No entrena: {percent(rejected_share)} de las filas no pasan las reglas de calidad "
            f"(máximo {percent(t.max_rejected_share)}).",
        )

    accumulated = signals.accumulated_valid_rows
    share = signals.valid_rows / accumulated if accumulated else None
    if signals.valid_rows < t.min_valid_rows or (
        share is not None and share < t.min_share_of_accumulated
    ):
        size = f"{integer(signals.valid_rows)} filas válidas"
        if share is not None:
            size += f", {percent(share)} del acumulado"
        return _skip(
            "small_batch",
            f"No entrena: lote pequeño ({size}; mínimo {integer(t.min_valid_rows)} filas y "
            f"{percent(t.min_share_of_accumulated, 0)} del acumulado)."
            + _new_categories_note(signals),
        )

    if not signals.has_champion:
        return TrainingDecision(
            True, "baseline", ["baseline"], "Entrena: línea base, no hay modelo productivo."
        )

    fired: list[str] = []
    parts: list[str] = []

    drifted = {c: v for c, v in signals.drift_psi.items() if v is not None and v > t.psi}
    if drifted:
        fired += [f"drift:{c}" for c in drifted]
        parts.append("drift en " + ", ".join(f"{c} (PSI {decimal(v)})" for c, v in drifted.items()))

    new = {
        c: s
        for c, s in signals.new_category_share.items()
        if c in SIGNAL_CATEGORY_COLUMNS and s >= t.new_category_share
    }
    if new:
        fired += [f"new_categories:{c}" for c in new]
        parts.append(
            "categorías nuevas en "
            + ", ".join(f"{c} ({percent(s)} del lote)" for c, s in new.items())
        )

    if signals.rows_at_last_training:
        growth = (accumulated + signals.valid_rows) / signals.rows_at_last_training - 1
        if growth >= t.volume_growth:
            fired.append("volume_growth")
            parts.append(f"el acumulado creció {percent(growth, 0)} desde el último entrenamiento")

    if signals.champion_mape_on_batch is not None and signals.champion_reference_mape:
        on_batch = signals.champion_mape_on_batch
        reference = signals.champion_reference_mape
        ratio = on_batch / reference
        if ratio >= t.degradation_factor:
            fired.append("champion_degradation")
            parts.append(
                f"el MAPE del modelo productivo en el lote ({percent(on_batch)}) es "
                f"{decimal(ratio)} veces su referencia ({percent(reference)})"
            )

    if signals.inference_events >= t.min_inference_events:
        inference = {
            c: v for c, v in signals.inference_psi.items() if v is not None and v > t.inference_psi
        }
        if inference:
            fired += [f"inference_drift:{c}" for c in inference]
            parts.append(
                "las consultas reales cambiaron en "
                + ", ".join(f"{c} (PSI {decimal(v)})" for c, v in inference.items())
            )

    if fired:
        return TrainingDecision(True, "signals", fired, "Entrena: " + "; ".join(parts) + ".")
    return _skip(
        "no_change",
        "No entrena: sin drift relevante, sin categorías nuevas frecuentes, sin crecimiento "
        "suficiente del volumen y sin degradación del modelo productivo.",
    )
