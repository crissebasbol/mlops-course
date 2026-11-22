"""Simulación offline del pipeline sobre los lotes descargados con fetch_batches.py.

Aplica la misma lógica del DAG (paquete housing_ml) sin Airflow ni MLflow para calibrar
umbrales y medir tiempo y memoria del entrenamiento.

Uso:
    uv run python scripts/simulate_batches.py --batches-dir data/batches --out data/simulation
"""

import argparse
import json
import resource
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

from housing_ml.cleaning import normalize, quality_flags, quality_report
from housing_ml.decision import BatchSignals, decide_training
from housing_ml.drift import new_categories, numeric_drift
from housing_ml.features import MODEL_INPUT_COLUMNS, assign_splits, payload_hash, row_hash
from housing_ml.formatting import percent
from housing_ml.gates import EvaluationSet, compare_models
from housing_ml.metrics import price_band, regression_metrics, size_band
from housing_ml.model import build_model, iterations
from housing_ml.schema import validate_schema

CATEGORY_COLUMNS = ("status", "state", "city", "zip_code", "brokered_by")


def peak_memory_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1e6 if sys.platform == "darwin" else peak / 1e3


def evaluate(model, frame: pd.DataFrame) -> dict:
    return regression_metrics(frame["price"], model.predict(frame[list(MODEL_INPUT_COLUMNS)]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batches-dir", type=Path, default=Path("data/batches"))
    parser.add_argument("--out", type=Path, default=Path("data/simulation"))
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--ingestion-date", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    files = sorted(args.batches_dir.glob("batch_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    accumulated = pd.DataFrame()
    seen: dict[str, int] = {}
    champion, champion_reference, champion_batch = None, None, None
    rows_at_last_training, pending = None, []
    results = []

    for cycle in range(1, args.cycles + 1):
        for path in files:
            body = json.loads(path.read_text())
            if "data" not in body:
                continue
            records, batch = body["data"], body["batch_number"]
            data_hash = payload_hash(records)
            row = {"cycle": cycle, "batch": batch, "rows": len(records)}
            print(f"\n=== ciclo {cycle}, lote {batch}: {len(records)} filas")

            if data_hash in seen:
                holdout = accumulated[
                    (accumulated["batch"] == seen[data_hash]) & (accumulated["split"] == "holdout")
                ]
                monitoring = evaluate(champion, holdout) if champion is not None else None
                row.update(outcome="duplicate", training="-", promotion="-")
                row["monitoring_mape"] = monitoring and monitoring["mape"]
                print(
                    f"Duplicado del lote {seen[data_hash]}; MAPE del champion en su holdout: "
                    f"{monitoring and percent(monitoring['mape'], 2)}"
                )
                results.append(row)
                continue
            seen[data_hash] = batch

            started = time.perf_counter()
            raw = pd.DataFrame(records)
            schema = validate_schema(raw)
            clean = normalize(raw, args.ingestion_date)
            flags = quality_flags(clean)
            quality = quality_report(raw, clean, flags)
            valid = ~flags.any(axis=1)
            hashes = pd.Series([row_hash(r) for r in records], index=raw.index)
            batch_clean = clean[valid].assign(
                row_hash=hashes[valid], split=assign_splits(hashes[valid]), batch=batch
            )

            categories, drift = {}, {}
            if not accumulated.empty:
                categories = {
                    c: new_categories(accumulated[c], batch_clean[c]) for c in CATEGORY_COLUMNS
                }
                drift = numeric_drift(accumulated, batch_clean)
            champion_on_batch = evaluate(champion, batch_clean) if champion is not None else None

            signals = BatchSignals(
                schema_status=schema.status,
                valid_rows=quality["valid_rows"],
                rejected_rows=quality["rejected_rows"],
                accumulated_valid_rows=len(accumulated),
                rows_at_last_training=rows_at_last_training,
                has_champion=champion is not None,
                drift_psi={c: d["psi"] for c, d in drift.items()},
                new_category_share={c: v["row_share"] for c, v in categories.items()},
                champion_mape_on_batch=champion_on_batch and champion_on_batch["mape"],
                champion_reference_mape=champion_reference,
            )
            decision = decide_training(signals)
            accumulated = pd.concat([accumulated, batch_clean], ignore_index=True)
            pending.append(batch)
            prep_seconds = time.perf_counter() - started
            print(
                f"Esquema {schema.status}; válidas {quality['valid_rows']}, rechazadas "
                f"{quality['rejected_rows']} {quality['rejections_by_reason']}"
            )
            print("PSI:", {c: d["psi"] for c, d in drift.items()})
            print("Nuevas:", {c: v["row_share"] for c, v in categories.items()})
            print(decision.reason)
            row.update(
                outcome="new",
                valid=quality["valid_rows"],
                rejected=quality["rejected_rows"],
                schema=schema.status,
                training=decision.code,
                signals=",".join(decision.signals),
                training_reason=decision.reason,
                prep_seconds=round(prep_seconds, 1),
                champion_mape_on_batch=champion_on_batch and champion_on_batch["mape"],
            )

            if decision.train:
                train = accumulated[accumulated["split"] == "train"]
                started = time.perf_counter()
                model = build_model().fit(train[list(MODEL_INPUT_COLUMNS)], train["price"])
                train_seconds = time.perf_counter() - started
                metrics = {
                    split: evaluate(model, accumulated[accumulated["split"] == split])
                    for split in ("train", "val", "test")
                }
                holdout = accumulated[accumulated["split"] == "holdout"].reset_index(drop=True)
                evaluation = EvaluationSet(
                    X=holdout[list(MODEL_INPUT_COLUMNS)],
                    y=holdout["price"].to_numpy(),
                    recent=holdout["batch"].isin(pending).to_numpy(),
                    segments={
                        "status": holdout["status"],
                        "state": holdout["state"],
                        "size_band": size_band(holdout["house_size"]),
                    },
                    diagnostic_segments={"price_band": price_band(holdout["price"])},
                )
                promotion = compare_models(model, champion, evaluation)
                print(
                    f"Entrenado en {train_seconds:.0f} s con {len(train)} filas, "
                    f"{iterations(model)} iteraciones; val MAPE "
                    f"{percent(metrics['val']['mape'], 2)}"
                )
                for gate in promotion.gates:
                    print(("  OK  " if gate.passed else "  NO  ") + gate.message)
                for item in promotion.diagnostics:
                    champ = item["champion"]
                    print(
                        f"  diagnóstico {item['segment']}: {percent(item['candidate'], 2)} frente "
                        f"a {percent(champ, 2) if champ is not None else '-'}"
                    )
                print(promotion.reason)
                row.update(
                    train_rows=len(train),
                    train_seconds=round(train_seconds, 1),
                    iterations=iterations(model),
                    val_mape=metrics["val"]["mape"],
                    test_mape=metrics["test"]["mape"],
                    candidate_mape=promotion.candidate_metrics["mape"],
                    champion_mape=promotion.champion_metrics and promotion.champion_metrics["mape"],
                    promotion="promoted" if promotion.promote else "rejected",
                    promotion_reason=promotion.reason,
                    gates={g.gate: g.passed for g in promotion.gates},
                    latency_p95_ms=promotion.gate("G6_budget").detail["latency_p95_ms"],
                    size_mb=promotion.gate("G6_budget").detail["size_mb"],
                )
                if promotion.promote:
                    champion, champion_batch = model, batch
                    champion_reference = promotion.candidate_metrics["mape"]
                rows_at_last_training, pending = len(accumulated), []
            else:
                row["promotion"] = "-"
            row["champion_batch"] = champion_batch
            row["peak_memory_mb"] = round(peak_memory_mb())
            results.append(row)

    (args.out / "results.json").write_text(json.dumps(results, indent=2, default=str))
    lines = [
        "| Ciclo | Lote | Filas | Válidas | Entrenamiento | Señales | Promoción "
        "| MAPE candidato | MAPE productivo | Entrenamiento (s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        cand = r.get("candidate_mape")
        champ = r.get("champion_mape")
        lines.append(
            f"| {r['cycle']} | {r['batch']} | {r['rows']} | {r.get('valid', '-')} "
            f"| {r['training']} | {r.get('signals', '') or '-'} | {r['promotion']} "
            f"| {percent(cand, 2) if cand else '-'} | {percent(champ, 2) if champ else '-'} "
            f"| {r.get('train_seconds', '-')} |"
        )
    (args.out / "results.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    print(f"\nMemoria pico: {peak_memory_mb():.0f} MB")


if __name__ == "__main__":
    main()
