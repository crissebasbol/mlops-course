PRECIO_M2_POR_ESTRATO = {
    1: 2_000_000,
    2: 2_800_000,
    3: 3_800_000,
    4: 4_500_000,
    5: 6_500_000,
    6: 8_000_000,
}
DESCUENTO_APRETADO = 0.95


class PriceModel:
    version = "reglas-1.0"

    def predict(self, features: dict) -> float:
        precio = (
            features["area_m2"]
            * PRECIO_M2_POR_ESTRATO[features["estrato"]]
            * features["factor_zona"]
        )
        if features["es_apretado"]:
            precio *= DESCUENTO_APRETADO
        return round(precio, 0)


_model = PriceModel()


def get_model() -> PriceModel:
    return _model
