import numpy as np
import pytest
from api_fakes import (
    ADMIN_TOKEN,
    FakeRegistry,
    FakeSink,
    fake_explainer_factory,
    train_models,
)
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from housing_api.config import Settings
from housing_api.explain import Explainer
from housing_api.main import create_app
from housing_api.schemas import EXAMPLE


@pytest.fixture(scope="session")
def models() -> dict:
    return train_models()


@pytest.fixture
def registry(models) -> FakeRegistry:
    return FakeRegistry(models)


@pytest.fixture
def sink() -> FakeSink:
    return FakeSink()


@pytest.fixture
def make_client(registry, sink):
    clients = []

    def make(admin_token: str = ADMIN_TOKEN) -> TestClient:
        app = create_app(
            Settings(admin_token=admin_token),
            registry,
            sink,
            Explainer(fake_explainer_factory),
            background=False,
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


def metric(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def refresh(client):
    return client.app.state.manager.refresh()


def logged(client, sink) -> list[dict]:
    client.app.state.logger.flush()
    return sink.events


def admin(token: str = ADMIN_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_503_without_champion(make_client, sink):
    client = make_client()
    refresh(client)
    assert client.get("/health").json() == {
        "status": "ok",
        "model_loaded": False,
        "champion_version": None,
        "shadow_version": None,
    }
    response = client.post("/predict", json=EXAMPLE)
    assert response.status_code == 503
    [event] = logged(client, sink)
    assert (event["status"], event["status_code"]) == ("no_model", 503)


def test_predict_logs_request_and_traffic_source(make_client, registry, sink):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    response = client.post("/predict", json=EXAMPLE, headers={"X-Traffic-Source": "streamlit"})
    body = response.json()
    assert response.status_code == 200
    assert (body["model_version"], body["model_alias"]) == (1, "champion")
    assert body["predicted_price"] > 0
    [event] = logged(client, sink)
    assert event["request_id"] == body["request_id"]
    assert (event["status"], event["traffic_source"], event["champion_version"]) == (
        "ok",
        "streamlit",
        1,
    )
    assert event["request"]["house_size"] == EXAMPLE["house_size"]
    assert event["prediction"] == body["predicted_price"]
    assert event.get("shadow_version") is None


def test_invalid_input_is_rejected_and_logged(make_client, registry, sink):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    response = client.post(
        "/predict", json={**EXAMPLE, "house_size": 50}, headers={"X-Traffic-Source": "otro"}
    )
    assert response.status_code == 422
    [event] = logged(client, sink)
    assert (event["status"], event["traffic_source"]) == ("invalid_input", "api")
    assert "house_size" in event["error"]


def test_numeric_zip_and_broker_are_normalized(make_client, registry):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    response = client.post("/predict", json={**EXAMPLE, "zip_code": 1109, "brokered_by": 22611})
    assert response.status_code == 200
    bad_date = client.post("/predict", json={**EXAMPLE, "prev_sold_date": "1850-01-01"})
    assert bad_date.status_code == 422


def test_shadow_prediction_is_saved_with_the_champion(make_client, registry, sink):
    registry.aliases.update(champion=1, challenger=2)
    client = make_client()
    refresh(client)
    before = metric("predictions_total", model_role="shadow")
    client.post("/predict", json=EXAMPLE, headers={"X-Replay-Row": "a" * 64})
    [event] = logged(client, sink)
    assert (event["champion_version"], event["shadow_version"]) == (1, 2)
    assert event["shadow_prediction"] > 0 and event["shadow_latency_ms"] > 0
    assert event["replay_row_hash"] == "a" * 64
    assert metric("predictions_total", model_role="shadow") == before + 1


def test_promotion_is_picked_up_without_restart(make_client, registry):
    registry.aliases.update(champion=1, challenger=2)
    client = make_client()
    refresh(client)
    registry.aliases.update(champion=2, previous_champion=1)
    result = refresh(client)
    assert (result.champion_before, result.champion_after) == (1, 2)
    assert client.post("/predict", json=EXAMPLE).json()["model_version"] == 2
    assert client.get("/health").json()["shadow_version"] is None
    assert registry.loads == [1, 2]


def test_failed_download_keeps_serving_the_previous_model(make_client, registry):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    before = metric("model_reload_failures_total", role="champion")
    registry.aliases["champion"] = 3
    registry.fail_load.add(3)
    result = refresh(client)
    assert result.errors and result.champion_after == 1
    assert client.post("/predict", json=EXAMPLE).json()["model_version"] == 1
    assert metric("model_reload_failures_total", role="champion") == before + 1


def test_rollback_requires_token_and_moves_aliases(make_client, registry, sink):
    registry.aliases.update(champion=2, previous_champion=1, challenger=2)
    client = make_client()
    refresh(client)
    body = {"reason": "Sube el error en producción", "actor": "fabian"}
    assert client.post("/admin/rollback", json=body).status_code == 401
    assert client.post("/admin/rollback", json=body, headers=admin("otro")).status_code == 401
    response = client.post("/admin/rollback", json=body, headers=admin())
    assert response.status_code == 200
    assert response.json() == {
        "action": "rollback",
        "from_version": 2,
        "to_version": 1,
        "audit_logged": True,
    }
    assert (registry.aliases["champion"], registry.aliases["previous_champion"]) == (1, 2)
    assert sink.actions[-1][:4] == ("rollback", 2, 1, "fabian")
    assert (2, "rolled_back") in registry.tags
    health = client.get("/health").json()
    assert (health["champion_version"], health["shadow_version"]) == (1, 2)


def test_rollback_without_previous_version_is_a_conflict(make_client, registry):
    registry.aliases["champion"] = 1
    client = make_client()
    response = client.post("/admin/rollback", json={"reason": "prueba"}, headers=admin())
    assert response.status_code == 409


def test_admin_is_disabled_without_token(make_client):
    client = make_client(admin_token="")
    assert client.post("/admin/reload", headers=admin()).status_code == 503


def test_forced_reload_is_audited(make_client, registry, sink):
    registry.aliases["champion"] = 1
    client = make_client()
    response = client.post("/admin/reload", headers=admin())
    assert response.json()["to_version"] == 1
    assert sink.actions[-1][:4] == ("reload", None, 1, "admin")


def test_feedback_is_stored(make_client, sink):
    client = make_client()
    body = {"request_id": "6f1c1b7e-8d0a-4c56-9a3e-2f0d9c1b2a33", "actual_price": 350000}
    assert client.post("/feedback", json=body).status_code == 202
    assert sink.feedback == [(body["request_id"], 350000.0, "api")]
    sink.fail = True
    assert client.post("/feedback", json=body).status_code == 503


def test_explain_returns_effects_on_price(make_client, registry):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    body = client.post("/explain", json=EXAMPLE).json()
    contributions = body["contributions"]
    assert body["model_version"] == 1
    assert np.isclose(body["base_price"], 300_000)
    assert [abs(c["shap_log"]) for c in contributions] == sorted(
        (abs(c["shap_log"]) for c in contributions), reverse=True
    )
    first = contributions[0]
    assert np.isclose(first["effect_pct"], np.expm1(first["shap_log"]) * 100)
    assert {c["feature"] for c in contributions} >= {"house_size", "state", "zip3"}


def test_database_failure_does_not_break_predictions(make_client, registry, sink):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    sink.fail = True
    before = metric("inference_log_errors_total", reason="database")
    assert client.post("/predict", json=EXAMPLE).status_code == 200
    client.app.state.logger.flush()
    assert metric("inference_log_errors_total", reason="database") == before + 1


def test_unknown_categories_are_counted(make_client, registry):
    registry.aliases["champion"] = 1
    client = make_client()
    refresh(client)
    before = metric("unknown_category_total", field="state")
    assert client.post("/predict", json={**EXAMPLE, "state": "Atlantis"}).status_code == 200
    assert metric("unknown_category_total", field="state") == before + 1


def test_model_info_and_metrics(make_client, registry):
    registry.aliases.update(champion=1, challenger=2)
    client = make_client()
    refresh(client)
    info = client.get("/model-info").json()
    assert (info["champion"]["version"], info["shadow"]["version"]) == (1, 2)
    assert info["champion"]["metrics"] == {"holdout_mape": 0.21}
    client.post("/predict", json=EXAMPLE)
    text = client.get("/metrics").text
    assert 'model_info{alias="champion",role="champion",version="1"} 1.0' in text
    assert 'http_requests_total{endpoint="/predict",status="200"}' in text
