import unicodedata

from errors import EmptyTextError, NotNumericError, OutOfRangeError

AREA_MIN, AREA_MAX = 20, 1000
HABITACIONES_MIN, HABITACIONES_MAX = 1, 10
ESTRATO_MIN, ESTRATO_MAX = 1, 6
AREA_POR_HABITACION_APRETADA = 20

FACTOR_ZONA = {
    "chapinero": 1.20,
    "usaquen": 1.15,
    "teusaquillo": 1.05,
    "suba": 0.95,
    "kennedy": 0.85,
    "bosa": 0.80,
}
FACTOR_ZONA_DEFAULT = 1.0


def clean_text(text: str, name: str = "texto") -> str:
    """Pasa a minúsculas, quita tildes y espacios repetidos."""
    if text is None or not text.strip():
        raise EmptyTextError(name)
    sin_tildes = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(sin_tildes.lower().split())


def validate_range(value: float, min_value: float, max_value: float, name: str = "valor") -> float:
    """Devuelve el valor si está en [min_value, max_value]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NotNumericError(name, value)
    if value < min_value or value > max_value:
        raise OutOfRangeError(name, value, min_value, max_value)
    return value


def transform_features(barrio: str, area_m2: float, habitaciones: int, estrato: int) -> dict:
    """Limpia, valida y calcula las features que usa el modelo."""
    barrio_limpio = clean_text(barrio, "barrio")
    validate_range(area_m2, AREA_MIN, AREA_MAX, "area_m2")
    validate_range(habitaciones, HABITACIONES_MIN, HABITACIONES_MAX, "habitaciones")
    validate_range(estrato, ESTRATO_MIN, ESTRATO_MAX, "estrato")

    area_por_habitacion = round(area_m2 / habitaciones, 2)
    return {
        "barrio": barrio_limpio,
        "area_m2": area_m2,
        "habitaciones": habitaciones,
        "estrato": estrato,
        "area_por_habitacion": area_por_habitacion,
        "es_apretado": area_por_habitacion < AREA_POR_HABITACION_APRETADA,
        "es_estrato_alto": estrato >= 5,
        "factor_zona": FACTOR_ZONA.get(barrio_limpio, FACTOR_ZONA_DEFAULT),
    }
