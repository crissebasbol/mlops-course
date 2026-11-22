from collections import Counter

import pandas as pd

from housing_ml.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    UNKNOWN,
    FeatureBuilder,
    assign_splits,
    payload_hash,
    row_hash,
)


def test_row_hash_ignores_key_order():
    assert row_hash({"a": 1, "b": "x"}) == row_hash({"b": "x", "a": 1})
    assert row_hash({"a": 1}) != row_hash({"a": 2})


def test_payload_hash_detects_repeated_batches(records):
    assert payload_hash(records) == payload_hash([dict(r) for r in records])
    assert payload_hash(records) != payload_hash(records[1:])


def test_splits_are_stable_and_balanced(records):
    hashes = pd.Series([row_hash(r) for r in records])
    first, second = assign_splits(hashes), assign_splits(hashes)
    assert first.equals(second)
    shares = {k: v / len(records) for k, v in Counter(first).items()}
    assert 0.6 < shares["train"] < 0.8
    assert 0.05 < shares["holdout"] < 0.15


def test_feature_builder_derives_features(raw):
    features = FeatureBuilder().fit_transform(raw.head(5))
    assert list(features.columns) == list(NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    assert features["zip_code"].str.len().eq(5).all()
    assert features["zip3"].str.len().eq(3).all()
    assert features["city_state"].str.contains(", ").all()


def test_feature_builder_handles_missing_and_unknown_values():
    row = pd.DataFrame([{"status": None, "state": "Nowhere", "city": None, "bed": 2}])
    features = FeatureBuilder().transform(row)
    assert features.loc[0, "status"] == UNKNOWN
    assert features.loc[0, "city_state"] == UNKNOWN
    assert features.loc[0, "zip_code"] == UNKNOWN
    assert pd.isna(features.loc[0, "house_size"])
