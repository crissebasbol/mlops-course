import hashlib
import json
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from housing_ml.cleaning import clean_text, column, normalize_code, normalize_zip

MODEL_INPUT_COLUMNS = (
    "status",
    "bed",
    "bath",
    "acre_lot",
    "house_size",
    "prev_sold_date",
    "city",
    "state",
    "zip_code",
    "brokered_by",
)
NUMERIC_FEATURES = ("bed", "bath", "acre_lot", "house_size", "prev_sold_year")
CATEGORICAL_FEATURES = ("status", "state", "city_state", "zip_code", "zip3", "brokered_by")
UNKNOWN = "unknown"
SPLIT_CUTS = (("train", 70), ("val", 80), ("test", 90), ("holdout", 100))


def canonical_json(record: dict) -> str:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )


def row_hash(record: dict) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def payload_hash(records: Iterable[dict]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(canonical_json(record).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def split_for(hash_hex: str) -> str:
    bucket = int(hash_hex[:8], 16) % 100
    return next(name for name, cut in SPLIT_CUTS if bucket < cut)


def assign_splits(hashes: pd.Series) -> pd.Series:
    return hashes.map(split_for)


def _category(values: pd.Series) -> pd.Series:
    return values.astype(object).where(values.notna(), UNKNOWN)


class FeatureBuilder(TransformerMixin, BaseEstimator):
    def fit(self, X, y=None):
        return self

    def transform(self, X) -> pd.DataFrame:
        frame = pd.DataFrame(X).reset_index(drop=True)
        features = pd.DataFrame(index=frame.index)
        for name in ("bed", "bath", "acre_lot", "house_size"):
            features[name] = pd.to_numeric(column(frame, name), errors="coerce").astype(float)
        dates = pd.to_datetime(column(frame, "prev_sold_date"), errors="coerce", format="ISO8601")
        features["prev_sold_year"] = dates.dt.year.astype(float)

        status = clean_text(column(frame, "status"), lower=True)
        state = clean_text(column(frame, "state"))
        city = clean_text(column(frame, "city"))
        zip_code = normalize_zip(column(frame, "zip_code"))
        features["status"] = _category(status)
        features["state"] = _category(state)
        features["city_state"] = _category(city.str.cat(state, sep=", "))
        features["zip_code"] = _category(zip_code)
        features["zip3"] = _category(zip_code.str[:3])
        features["brokered_by"] = _category(normalize_code(column(frame, "brokered_by")))
        return features[list(NUMERIC_FEATURES + CATEGORICAL_FEATURES)]

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.asarray(NUMERIC_FEATURES + CATEGORICAL_FEATURES, dtype=object)
