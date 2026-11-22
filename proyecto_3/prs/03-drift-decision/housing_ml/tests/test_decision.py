import pytest

from housing_ml.decision import BatchSignals, decide_training


def signals(**overrides) -> BatchSignals:
    base = {
        "schema_status": "ok",
        "valid_rows": 90_000,
        "rejected_rows": 100,
        "accumulated_valid_rows": 400_000,
        "rows_at_last_training": 420_000,
        "has_champion": True,
        "drift_psi": {"price": 0.01, "house_size": 0.02},
        "new_category_share": {"status": 0.0, "state": 0.0, "city": 0.04},
        "champion_mape_on_batch": 0.20,
        "champion_reference_mape": 0.19,
    }
    return BatchSignals(**{**base, **overrides})


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"schema_status": "invalid"}, "invalid_schema"),
        ({"valid_rows": 0, "rejected_rows": 0}, "empty"),
        ({"valid_rows": 50_000, "rejected_rows": 20_000}, "low_quality"),
        ({"valid_rows": 4_000}, "small_batch"),
        ({"valid_rows": 15_000}, "small_batch"),
        ({"has_champion": False, "accumulated_valid_rows": 0}, "baseline"),
        ({}, "no_change"),
    ],
)
def test_decision_codes(overrides, code):
    assert decide_training(signals(**overrides)).code == code


def test_baseline_trains():
    decision = decide_training(
        signals(has_champion=False, accumulated_valid_rows=0, rows_at_last_training=None)
    )
    assert decision.train and decision.signals == ["baseline"]


def test_small_batch_with_new_state_does_not_train():
    decision = decide_training(
        signals(valid_rows=4_000, new_category_share={"state": 1.0}, accumulated_valid_rows=398_000)
    )
    assert not decision.train
    assert "Massachusetts" not in decision.reason
    assert "state (100,0 % del lote)" in decision.reason


def test_drift_triggers_training():
    decision = decide_training(signals(drift_psi={"house_size": 8.3, "price": 0.1}))
    assert decision.train
    assert decision.signals == ["drift:house_size"]
    assert "house_size (PSI 8,30)" in decision.reason


def test_new_status_and_volume_trigger_training():
    decision = decide_training(
        signals(
            valid_rows=230_000,
            accumulated_valid_rows=168_000,
            rows_at_last_training=168_000,
            new_category_share={"status": 1.0, "city": 0.02},
        )
    )
    assert decision.signals == ["new_categories:status", "volume_growth"]


def test_high_cardinality_categories_are_not_signals():
    decision = decide_training(signals(new_category_share={"city": 0.5, "zip_code": 0.3}))
    assert not decision.train


def test_champion_degradation_triggers_training():
    decision = decide_training(signals(champion_mape_on_batch=0.6, champion_reference_mape=0.15))
    assert decision.signals == ["champion_degradation"]


def test_inference_drift_needs_enough_events():
    quiet = signals(inference_psi={"house_size": 0.5}, inference_events=100)
    busy = signals(inference_psi={"house_size": 0.5}, inference_events=800)
    assert not decide_training(quiet).train
    assert decide_training(busy).signals == ["inference_drift:house_size"]
