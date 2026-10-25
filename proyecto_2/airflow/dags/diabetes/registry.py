import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from .config import CHALLENGER_ALIAS, CHAMPION_ALIAS, MIN_IMPROVEMENT, MODEL_NAME, SELECTION_METRIC
from .training import score


def register_candidates(candidates: list[dict], batch_id: int) -> list[dict]:
    """Registra cada candidato como una nueva version de MODEL_NAME."""
    client = MlflowClient()
    registered = []
    for candidate in candidates:
        mv = mlflow.register_model(candidate["model_uri"], MODEL_NAME)
        client.set_model_version_tag(MODEL_NAME, mv.version, "model_type", candidate["model_type"])
        client.set_model_version_tag(MODEL_NAME, mv.version, "batch_id", str(batch_id))
        client.set_model_version_tag(MODEL_NAME, mv.version, SELECTION_METRIC, f"{candidate['score']:.4f}")
        client.update_model_version(
            MODEL_NAME,
            mv.version,
            description=(
                f"{candidate['model_type']} entrenado hasta el lote {batch_id}. "
                f"{SELECTION_METRIC}={candidate['score']:.4f}, test_f1_macro={candidate['test_f1_macro']:.4f}"
            ),
        )
        registered.append({**candidate, "version": int(mv.version)})
    return registered


def current_champion() -> dict | None:
    client = MlflowClient()
    try:
        mv = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
    except MlflowException:
        return None
    return {"version": int(mv.version), "run_id": mv.run_id}


def compare(registered: list[dict], val: pd.DataFrame) -> dict:
    """Mejor candidato del run vs champion actual, ambos medidos sobre el mismo
    split de validacion actual (el champion se re-evalua con los datos nuevos)."""
    best = max(registered, key=lambda c: c["score"])
    champion = current_champion()
    decision = {
        "best_version": best["version"],
        "best_model_type": best["model_type"],
        "best_score": best["score"],
        "champion_version": None,
        "champion_score": None,
        "promote": True,
    }
    if champion is None:
        return decision

    model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{champion['version']}")
    champion_score = score(model, val)
    decision.update({
        "champion_version": champion["version"],
        "champion_score": champion_score,
        "promote": best["version"] != champion["version"] and best["score"] > champion_score + MIN_IMPROVEMENT,
    })
    return decision


def promote(decision: dict) -> dict:
    """Mueve los alias: challenger siempre al mejor del run; champion solo si mejora."""
    client = MlflowClient()
    client.set_registered_model_alias(MODEL_NAME, CHALLENGER_ALIAS, str(decision["best_version"]))
    if decision["promote"]:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, str(decision["best_version"]))
        client.set_model_version_tag(MODEL_NAME, str(decision["best_version"]), "promoted", "true")
    champion = current_champion()
    return {**decision, "champion_after": champion["version"] if champion else None}
