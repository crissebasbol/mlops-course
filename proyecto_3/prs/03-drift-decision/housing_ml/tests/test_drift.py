import numpy as np
import pandas as pd

from housing_ml.drift import category_psi, ks, new_categories, numeric_drift, psi


def test_psi_is_small_for_same_distribution():
    rng = np.random.default_rng(0)
    reference = pd.Series(rng.normal(0, 1, 20_000))
    current = pd.Series(rng.normal(0, 1, 20_000))
    assert psi(reference, current) < 0.05


def test_psi_detects_shift():
    rng = np.random.default_rng(0)
    reference = pd.Series(rng.normal(0, 1, 20_000))
    current = pd.Series(rng.normal(2, 1, 20_000))
    assert psi(reference, current) > 0.2
    statistic, pvalue = ks(reference, current)
    assert statistic > 0.5 and pvalue < 0.01


def test_psi_handles_constant_reference():
    assert psi(pd.Series([3.0] * 100), pd.Series([3.0] * 100)) < 0.01
    assert psi(pd.Series([3.0] * 100), pd.Series([1.0] * 100)) > 0.2


def test_numeric_drift_report_flags_columns():
    reference = pd.DataFrame({"price": np.arange(1_000.0), "bed": np.ones(1_000)})
    current = pd.DataFrame({"price": np.arange(1_000.0) + 5_000, "bed": np.ones(1_000)})
    report = numeric_drift(reference, current, columns=("price", "bed"))
    assert report["price"]["drift"] is True
    assert report["bed"]["drift"] is False


def test_new_categories_share():
    reference = pd.Series(["for_sale"] * 10)
    current = pd.Series(["sold"] * 3 + ["for_sale"] * 7)
    result = new_categories(reference, current)
    assert result == {"new_values": 1, "row_share": 0.3, "examples": ["sold"]}
    assert category_psi(reference, current) > 0.2
