import io
from pathlib import Path

import pandas as pd
from airflow.providers.postgres.hooks.postgres import PostgresHook

from .config import (
    CLEAN_TABLE,
    CSV_COLUMNS,
    DATA_CONN_ID,
    NUMERIC_FEATURES,
    RAW_TABLE,
)

TRAINING_COLUMNS = ["species", "island", "sex"] + NUMERIC_FEATURES


class PenguinsDatabase:
    """Operaciones sobre las tablas raw_penguins y clean_penguins"""

    def __init__(self, conn_id: str = DATA_CONN_ID):
        self.conn_id = conn_id
        self._hook = None

    @property
    def hook(self) -> PostgresHook:
        if self._hook is None:
            self._hook = PostgresHook(postgres_conn_id=self.conn_id)
        return self._hook

    def _consultar(self, sql: str) -> pd.DataFrame:
        """Ejecuta una consulta y arma el DataFrame con el resultado."""
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                columnas = [descripcion[0] for descripcion in cur.description]
                return pd.DataFrame(cur.fetchall(), columns=columnas)
        finally:
            conn.close()

    def _copiar(self, sql: str, fuente) -> None:
        """Ejecuta un COPY ... FROM STDIN leyendo de un archivo o un buffer"""
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                cur.copy_expert(sql, fuente)
            conn.commit()
        finally:
            conn.close()

    def reset_tables(self) -> None:
        """Deja la base vacia: borra las tablas y las vuelve a crear."""
        self.hook.run(f"""
        DROP TABLE IF EXISTS {RAW_TABLE};
        DROP TABLE IF EXISTS {CLEAN_TABLE};

        CREATE TABLE {RAW_TABLE} (
            rowid             TEXT,
            species           TEXT,
            island            TEXT,
            bill_length_mm    TEXT,
            bill_depth_mm     TEXT,
            flipper_length_mm TEXT,
            body_mass_g       TEXT,
            sex               TEXT,
            year              TEXT,
            ingested_at       TIMESTAMPTZ DEFAULT now()
        );

        CREATE TABLE {CLEAN_TABLE} (
            id                SERIAL PRIMARY KEY,
            species           TEXT             NOT NULL,
            island            TEXT             NOT NULL,
            sex               TEXT             NOT NULL,
            bill_length_mm    DOUBLE PRECISION NOT NULL,
            bill_depth_mm     DOUBLE PRECISION NOT NULL,
            flipper_length_mm DOUBLE PRECISION NOT NULL,
            body_mass_g       DOUBLE PRECISION NOT NULL,
            year              INTEGER,
            processed_at      TIMESTAMPTZ DEFAULT now()
        );
        """)

    def count(self, table: str) -> int:
        return int(self.hook.get_first(f"SELECT count(*) FROM {table};")[0])

    def load_csv(self, csv_path: Path) -> int:
        """Copia el CSV a raw_penguins con COPY, sin transformar nada."""
        if not csv_path.exists():
            raise FileNotFoundError(f"No se encontro el CSV en {csv_path}")

        columnas = ", ".join(CSV_COLUMNS)
        with csv_path.open("r", encoding="utf-8") as fh:
            self._copiar(
                f"COPY {RAW_TABLE} ({columnas}) FROM STDIN WITH (FORMAT csv, HEADER true)",
                fh,
            )
        return self.count(RAW_TABLE)

    def read_raw(self) -> pd.DataFrame:
        return self._consultar(f"SELECT * FROM {RAW_TABLE};")

    def write_clean(self, df: pd.DataFrame) -> int:
        """Inserta el DataFrame limpio con COPY, igual que los datos crudos"""
        buffer = io.StringIO()
        df.to_csv(buffer, index=False, header=False)
        buffer.seek(0)

        columnas = ", ".join(df.columns)
        self._copiar(
            f"COPY {CLEAN_TABLE} ({columnas}) FROM STDIN WITH (FORMAT csv)",
            buffer,
        )
        return self.count(CLEAN_TABLE)

    def read_clean(self) -> pd.DataFrame:
        """Devuelve los datos listos para entrenar (sin columnas de control)."""
        columnas = ", ".join(TRAINING_COLUMNS)
        df = self._consultar(f"SELECT {columnas} FROM {CLEAN_TABLE};")
        if df.empty:
            raise ValueError(f"La tabla '{CLEAN_TABLE}' esta vacia, no hay con que entrenar.")
        return df
