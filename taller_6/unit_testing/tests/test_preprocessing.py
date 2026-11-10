import pytest

from errors import EmptyTextError, NotNumericError, OutOfRangeError, PreprocessingError
from preprocessing import clean_text, transform_features, validate_range


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("  Chapinero ", "chapinero"),
        ("USAQUÉN", "usaquen"),
        ("Santa   Bárbara", "santa barbara"),
    ],
)
def test_clean_text_normaliza(entrada, esperado):
    assert clean_text(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "   ", None])
def test_clean_text_vacio_lanza_error(entrada):
    with pytest.raises(EmptyTextError, match="barrio no puede estar vacío") as exc_info:
        clean_text(entrada, "barrio")
    assert exc_info.value.field == "barrio"


@pytest.mark.parametrize("valor", [80, 20, 1000])
def test_validate_range_valor_normal(valor):
    assert validate_range(valor, 20, 1000) == valor


@pytest.mark.parametrize("valor", [19.99, 1000.01, -5])
def test_validate_range_fuera_de_rango_lanza_error(valor):
    with pytest.raises(OutOfRangeError, match="area_m2 debe estar entre 20 y 1000") as exc_info:
        validate_range(valor, 20, 1000, "area_m2")
    error = exc_info.value
    assert (error.field, error.value, error.min_value, error.max_value) == ("area_m2", valor, 20, 1000)


@pytest.mark.parametrize("valor", ["80", None, True])
def test_validate_range_no_numerico_lanza_error(valor):
    with pytest.raises(NotNumericError, match="numérico") as exc_info:
        validate_range(valor, 20, 1000, "area_m2")
    assert exc_info.value.value == valor


def test_transform_features_caso_normal():
    features = transform_features("  Chapinero ", 80, 3, 4)
    assert features == {
        "barrio": "chapinero",
        "area_m2": 80,
        "habitaciones": 3,
        "estrato": 4,
        "area_por_habitacion": 26.67,
        "es_apretado": False,
        "es_estrato_alto": False,
        "factor_zona": 1.20,
    }


def test_transform_features_apretado_y_estrato_alto():
    features = transform_features("Usaquén", 50, 3, 5)
    assert features["area_por_habitacion"] == 16.67
    assert features["es_apretado"] is True
    assert features["es_estrato_alto"] is True
    assert features["factor_zona"] == 1.15


def test_transform_features_borde_area_por_habitacion_20_no_es_apretado():
    assert transform_features("suba", 60, 3, 3)["es_apretado"] is False


def test_transform_features_barrio_desconocido_usa_factor_1():
    assert transform_features("Barrio Nuevo", 80, 2, 3)["factor_zona"] == 1.0


@pytest.mark.parametrize(
    "kwargs, error_esperado, campo",
    [
        ({"habitaciones": 0}, OutOfRangeError, "habitaciones"),
        ({"habitaciones": 11}, OutOfRangeError, "habitaciones"),
        ({"estrato": 0}, OutOfRangeError, "estrato"),
        ({"estrato": 7}, OutOfRangeError, "estrato"),
        ({"area_m2": 5}, OutOfRangeError, "area_m2"),
        ({"area_m2": "80"}, NotNumericError, "area_m2"),
        ({"barrio": " "}, EmptyTextError, "barrio"),
    ],
)
def test_transform_features_entrada_invalida_lanza_error(kwargs, error_esperado, campo):
    datos = {"barrio": "suba", "area_m2": 80, "habitaciones": 2, "estrato": 3, **kwargs}
    with pytest.raises(error_esperado) as exc_info:
        transform_features(**datos)
    assert exc_info.value.field == campo
