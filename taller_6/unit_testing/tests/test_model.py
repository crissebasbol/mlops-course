import pytest

from model import PriceModel, get_model
from preprocessing import transform_features


@pytest.mark.parametrize(
    "barrio, area_m2, habitaciones, estrato, precio_esperado",
    [
        pytest.param("Chapinero", 80, 3, 4, 480_000_000, id="caso_normal"),
        pytest.param("Bosa", 50, 3, 2, 50 * 2_800_000 * 0.80 * 0.95, id="apretado_con_descuento"),
        pytest.param("Barrio Nuevo", 100, 2, 6, 800_000_000, id="barrio_desconocido"),
    ],
)
def test_precio(barrio, area_m2, habitaciones, estrato, precio_esperado):
    features = transform_features(barrio, area_m2, habitaciones, estrato)
    assert PriceModel().predict(features) == pytest.approx(precio_esperado)


def test_get_model_devuelve_siempre_la_misma_instancia():
    assert get_model() is get_model()
    assert isinstance(get_model(), PriceModel)
