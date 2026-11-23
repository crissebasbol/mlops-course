from types import SimpleNamespace

import numpy as np
import pandas as pd

from housing_api.registry import ModelRef
from housing_ml.features import MODEL_INPUT_COLUMNS
from housing_ml.model import build_model

ADMIN_TOKEN = "test-token"


def training_frame(n: int = 600, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "status": rng.choice(["for_sale", "sold"], n),
            "bed": rng.integers(1, 6, n).astype(float),
            "bath": rng.integers(1, 4, n).astype(float),
            "acre_lot": rng.uniform(0.05, 2, n),
            "house_size": rng.uniform(600, 4000, n),
            "prev_sold_date": rng.choice(["2010-01-01", "2015-06-15", None], n),
            "city": rng.choice(["Springfield", "Boston", "Hartford"], n),
            "state": rng.choice(["Massachusetts", "Connecticut"], n),
            "zip_code": rng.choice(["01109", "02108", "06103"], n),
            "brokered_by": rng.choice(["1", "2", "3"], n),
        }
    )
    price = 50_000 + frame["house_size"] * 150 + frame["bath"] * 10_000
    return frame[list(MODEL_INPUT_COLUMNS)], price + rng.normal(0, 5_000, n)


class FakeRegistry:
    def __init__(self, models: dict):
        self.models = models
        self.aliases: dict[str, int] = {}
        self.tags: dict = {}
        self.loads: list[int] = []
        self.fail_load: set[int] = set()

    def resolve(self, alias: str) -> ModelRef | None:
        version = self.aliases.get(alias)
        if version is None:
            return None
        return ModelRef(version, f"run-{version}", {"decision": "promoted"})

    def load(self, ref: ModelRef):
        if ref.version in self.fail_load:
            raise RuntimeError("descarga fallida")
        self.loads.append(ref.version)
        return self.models[ref.version]

    def run_metrics(self, run_id):
        return {"holdout_mape": 0.21}

    def set_alias(self, alias: str, version: int) -> None:
        self.aliases[alias] = version

    def tag_version(self, version: int, key: str, value: str) -> None:
        self.tags[(version, key)] = value


class FakeSink:
    def __init__(self):
        self.events: list[dict] = []
        self.feedback: list[tuple] = []
        self.actions: list[tuple] = []
        self.fail = False

    def write_events(self, events):
        if self.fail:
            raise RuntimeError("postgres caído")
        self.events.extend(events)

    def write_feedback(self, request_id, actual_price, source):
        if self.fail:
            raise RuntimeError("postgres caído")
        self.feedback.append((request_id, actual_price, source))

    def write_action(self, action, from_version, to_version, actor, reason):
        self.actions.append((action, from_version, to_version, actor, reason))


def fake_explainer_factory(estimator):
    def explain(encoded: pd.DataFrame):
        values = np.linspace(0.2, -0.1, encoded.shape[1]).reshape(1, -1)
        return SimpleNamespace(values=values, base_values=np.array([np.log1p(300_000)]))

    return explain


def train_models() -> dict:
    trained = {}
    for version, iterations in ((1, 20), (2, 40), (3, 60)):
        model = build_model({"max_iter": iterations, "early_stopping": False})
        model.fit(*training_frame(seed=version))
        trained[version] = model
    return trained
