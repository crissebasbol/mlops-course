import re

import numpy as np
import pandas as pd

from .config import N_COVER_TYPES, NUMERIC_FEATURES, TARGET, WILDERNESS_AREAS

SOIL_PATTERN = re.compile(r"^C\d{4}$")
_WILDERNESS = {w.lower(): w for w in WILDERNESS_AREAS}


class CovertypePreprocessor:
    """De filas crudas a filas tipadas y validadas.

    - Numericas: a float; lo que no es numero queda en NULL.
    - Wilderness_Area: se normaliza al nombre canonico; desconocido -> NULL.
    - Soil_Type: mayusculas y formato C####; si no cumple -> NULL. Codigos
      validos que nunca se vieron (p.ej. C5151) se conservan: el modelo los
      ignora al predecir.
    - Cover_Type: entero entre 0 y 6. Sin etiqueta valida la fila se descarta.

    Los NULL se quedan en la etapa procesada; la etapa de entrenamiento solo
    toma filas completas.
    """

    columnas_destino = ["row_hash", *NUMERIC_FEATURES, "wilderness_area", "soil_type", TARGET]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = self._castear_numericas(df)
        df = self._normalizar_categoricas(df)
        df = self._validar_etiqueta(df)
        return df[self.columnas_destino].reset_index(drop=True)

    def _a_numero(self, serie: pd.Series) -> pd.Series:
        return pd.to_numeric(serie.astype("string").str.strip(), errors="coerce").astype("float64")

    def _a_entero(self, serie: pd.Series) -> pd.Series:
        numeros = self._a_numero(serie)
        no_enteros = numeros.notna() & (numeros != np.floor(numeros))
        return numeros.mask(no_enteros).astype("Int64")

    def _castear_numericas(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in NUMERIC_FEATURES:
            df[col] = self._a_numero(df[col])
        return df

    def _normalizar_categoricas(self, df: pd.DataFrame) -> pd.DataFrame:
        wilderness = df["wilderness_area"].astype("string").str.strip().str.lower()
        df["wilderness_area"] = wilderness.map(_WILDERNESS).astype("string")

        suelo = df["soil_type"].astype("string").str.strip().str.upper()
        df["soil_type"] = suelo.where(suelo.str.match(SOIL_PATTERN.pattern).fillna(False))
        return df

    def _validar_etiqueta(self, df: pd.DataFrame) -> pd.DataFrame:
        df[TARGET] = self._a_entero(df[TARGET])
        valida = df[TARGET].between(0, N_COVER_TYPES - 1).fillna(False)
        return df[valida]
