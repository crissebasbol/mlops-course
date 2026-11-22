import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

DRIFT_COLUMNS = ("price", "house_size", "bed", "bath", "acre_lot")
EPSILON = 1e-4


def _sample(values: pd.Series, max_rows: int, seed: int) -> np.ndarray:
    values = values.dropna().to_numpy(dtype=float)
    if len(values) > max_rows:
        values = np.random.default_rng(seed).choice(values, max_rows, replace=False)
    return values


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float | None:
    ref = reference.dropna().to_numpy(dtype=float)
    cur = current.dropna().to_numpy(dtype=float)
    if len(ref) == 0 or len(cur) == 0:
        return None
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:
        edges = np.array([-np.inf, ref[0], np.inf])
    edges[0], edges[-1] = -np.inf, np.inf
    ref_share = np.clip(np.histogram(ref, edges)[0] / len(ref), EPSILON, None)
    cur_share = np.clip(np.histogram(cur, edges)[0] / len(cur), EPSILON, None)
    return float(np.sum((cur_share - ref_share) * np.log(cur_share / ref_share)))


def category_psi(reference: pd.Series, current: pd.Series) -> float | None:
    ref = reference.dropna().value_counts(normalize=True)
    cur = current.dropna().value_counts(normalize=True)
    if ref.empty or cur.empty:
        return None
    categories = ref.index.union(cur.index)
    ref_share = np.clip(ref.reindex(categories, fill_value=0).to_numpy(), EPSILON, None)
    cur_share = np.clip(cur.reindex(categories, fill_value=0).to_numpy(), EPSILON, None)
    return float(np.sum((cur_share - ref_share) * np.log(cur_share / ref_share)))


def ks(
    reference: pd.Series, current: pd.Series, max_rows: int = 50_000, seed: int = 42
) -> tuple[float | None, float | None]:
    ref = _sample(reference, max_rows, seed)
    cur = _sample(current, max_rows, seed + 1)
    if len(ref) == 0 or len(cur) == 0:
        return None, None
    result = ks_2samp(ref, cur)
    return float(result.statistic), float(result.pvalue)


def numeric_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    columns: tuple[str, ...] = DRIFT_COLUMNS,
    threshold: float = 0.2,
) -> dict[str, dict]:
    report = {}
    for name in columns:
        value = psi(reference[name], current[name])
        statistic, pvalue = ks(reference[name], current[name])
        report[name] = {
            "psi": None if value is None else round(value, 4),
            "ks": None if statistic is None else round(statistic, 4),
            "ks_pvalue": pvalue,
            "reference_median": _median(reference[name]),
            "current_median": _median(current[name]),
            "drift": value is not None and value > threshold,
        }
    return report


def new_categories(reference: pd.Series, current: pd.Series, examples: int = 10) -> dict:
    seen = set(reference.dropna().unique())
    present = current.dropna()
    unseen = present[~present.isin(seen)]
    counts = unseen.value_counts()
    return {
        "new_values": int(len(counts)),
        "row_share": round(float(len(unseen) / len(current)), 4) if len(current) else 0.0,
        "examples": [str(v) for v in counts.index[:examples]],
    }


def _median(values: pd.Series) -> float | None:
    values = values.dropna()
    return None if values.empty else float(values.median())
