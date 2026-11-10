import pytest
from fastapi.testclient import TestClient

from app import app
from model import get_model


class FakeModel:
    version = "fake"

    def __init__(self):
        self.calls = []

    def predict(self, features: dict) -> float:
        self.calls.append(features)
        return 123.0


@pytest.fixture
def fake_model():
    return FakeModel()


@pytest.fixture
def client(fake_model):
    app.dependency_overrides[get_model] = lambda: fake_model
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def vivienda_valida():
    return {"barrio": "  Chapinero ", "area_m2": 80, "habitaciones": 3, "estrato": 4}
