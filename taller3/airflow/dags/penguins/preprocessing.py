import pandas as pd

from .config import CATEGORICAL_FEATURES, NUMERIC_FEATURES

# Literales que el CSV usa para representar un dato faltante.
FALTANTES = {"na", "n/a", "nan", "none", "null", ""}

# Columnas de la tabla cruda que no van a la tabla limpia.
COLUMNAS_DESCARTADAS = ("rowid", "ingested_at")


class PenguinsPreprocessor:
    """Limpia el DataFrame crudo y deja las columnas de clean_penguins."""

    columnas_destino = ["species", "island", "sex"] + NUMERIC_FEATURES + ["year"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._descartar_columnas(df)
        df = self._castear_numericas(df)
        df = self._normalizar_categoricas(df)
        df = self._descartar_invalidas(df)
        return df[self.columnas_destino]

    # Pasos del preprocesamiento
    def _descartar_columnas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Quita las columnas que no aportan al modelo."""
        return df.drop(columns=[c for c in COLUMNAS_DESCARTADAS if c in df.columns])

    def _castear_numericas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pasa de TEXT a numero"""
        df = df.copy()
        for col in NUMERIC_FEATURES:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        return df

    def _normalizar_categoricas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpia el texto y convierte los literales de faltante en nulos."""
        df = df.copy()
        for col in ("species", "island", "sex"):
            df[col] = df[col].astype("string").str.strip().str.lower()
            df.loc[df[col].isin(FALTANTES), col] = pd.NA

        df["species"] = df["species"].str.capitalize()
        df["island"] = df["island"].str.capitalize()
        df.loc[~df["sex"].isin(["male", "female"]), "sex"] = pd.NA
        return df

    def _descartar_invalidas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Elimina filas incompletas y duplicadas."""
        obligatorias = NUMERIC_FEATURES + CATEGORICAL_FEATURES + ["species"]
        return df.dropna(subset=obligatorias).drop_duplicates().reset_index(drop=True)
