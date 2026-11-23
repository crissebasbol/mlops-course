import threading

import numpy as np
import pandas as pd

from housing_api.models import LoadedModel


def _tree_explainer(estimator):
    import shap

    return shap.TreeExplainer(estimator)


def _plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


class Explainer:
    """SHAP del árbol en escala log1p del precio, como en los artefactos de entrenamiento.
    El explainer se crea al primer uso de cada versión del champion."""

    def __init__(self, factory=_tree_explainer):
        self.factory = factory
        self._lock = threading.Lock()
        self._cached: tuple[int, object] | None = None

    def _get(self, loaded: LoadedModel, estimator):
        with self._lock:
            if self._cached is None or self._cached[0] != loaded.version:
                self._cached = (loaded.version, self.factory(estimator))
            return self._cached[1]

    def warm(self, loaded: LoadedModel) -> None:
        self._get(loaded, loaded.model.regressor_.named_steps["model"])

    def explain(self, loaded: LoadedModel, frame: pd.DataFrame) -> dict:
        steps = loaded.model.regressor_.named_steps
        features = steps["features"].transform(frame)
        encoded = steps["encode"].transform(features)
        explanation = self._get(loaded, steps["model"])(encoded)
        values = np.asarray(explanation.values)[0]
        base = float(np.ravel(explanation.base_values)[0])
        contributions = [
            {
                "feature": name,
                "value": _plain(features.iloc[0][name]),
                "shap_log": float(value),
                "effect_pct": float(np.expm1(value) * 100),
            }
            for name, value in zip(encoded.columns, values, strict=True)
        ]
        contributions.sort(key=lambda c: abs(c["shap_log"]), reverse=True)
        return {
            "model_version": loaded.version,
            "predicted_price": float(np.expm1(base + values.sum())),
            "base_price": float(np.expm1(base)),
            "contributions": contributions,
        }


def unknown_categories(model, frame: pd.DataFrame) -> list[str]:
    try:
        steps = model.regressor_.named_steps
        features = steps["features"].transform(frame)
        encoder = steps["encode"].named_transformers_["categorical"]
        return [
            name
            for name in encoder.feature_names_in_
            if features.iloc[0][name] not in encoder.mappings_[name]
        ]
    except (AttributeError, KeyError):
        return []
