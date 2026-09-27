import hashlib

import pandas as pd
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values

from .config import (
    CATEGORICAL_FEATURES,
    CLEAN_TABLE,
    DATA_CONN_ID,
    LOG_TABLE,
    NUMERIC_FEATURES,
    RAW_COLUMNS,
    RAW_TABLE,
    TARGET,
    TRAIN_FRACTION,
    TRAIN_TABLE,
)

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
CLEAN_COLUMNS = FEATURE_COLUMNS + [TARGET]

def row_hash(fila: list[str]) -> str:
    """Identidad de una fila: el md5 de sus valores crudos. Es la llave primaria
    en las tres etapas, asi una fila repetida entre peticiones no se duplica."""
    return hashlib.md5("|".join(str(v) for v in fila).encode("utf-8")).hexdigest()


class CovertypeDatabase:
    """Todo el SQL contra la base de datos `covertype`"""

    def __init__(self, conn_id: str = DATA_CONN_ID):
        self.conn_id = conn_id
        self._hook = None

    @property
    def hook(self) -> PostgresHook:
        if self._hook is None:
            self._hook = PostgresHook(postgres_conn_id=self.conn_id)
        return self._hook

    def _consultar(self, sql: str, params=None) -> pd.DataFrame:
        """Ejecuta una consulta y arma el DataFrame con el resultado."""
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columnas = [descripcion[0] for descripcion in cur.description]
                return pd.DataFrame(cur.fetchall(), columns=columnas)
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        """Crea las tablas si no existen"""
        raw_cols = ",\n".join(f"{c} TEXT" for c in RAW_COLUMNS)
        num_cols = ",\n".join(f"{c} DOUBLE PRECISION" for c in NUMERIC_FEATURES)
        num_cols_nn = ",\n".join(f"{c} DOUBLE PRECISION NOT NULL" for c in NUMERIC_FEATURES)

        self.hook.run(f"""
        CREATE TABLE IF NOT EXISTS {RAW_TABLE} (
            row_hash      TEXT PRIMARY KEY,
            {raw_cols},
            source        TEXT        NOT NULL,
            cycle         INTEGER     NOT NULL,
            batch_number  INTEGER     NOT NULL,
            dag_run_id    TEXT,
            ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at  TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS {RAW_TABLE}_pendientes_idx
            ON {RAW_TABLE} (ingested_at) WHERE processed_at IS NULL;

        CREATE TABLE IF NOT EXISTS {CLEAN_TABLE} (
            row_hash        TEXT PRIMARY KEY REFERENCES {RAW_TABLE} (row_hash),
            {num_cols},
            wilderness_area TEXT,
            soil_type       TEXT,
            cover_type      SMALLINT    NOT NULL,
            processed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS {TRAIN_TABLE} (
            row_hash        TEXT PRIMARY KEY REFERENCES {CLEAN_TABLE} (row_hash),
            {num_cols_nn},
            wilderness_area TEXT        NOT NULL,
            soil_type       TEXT        NOT NULL,
            cover_type      SMALLINT    NOT NULL,
            split           TEXT        NOT NULL CHECK (split IN ('train', 'test')),
            added_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            id             SERIAL PRIMARY KEY,
            dag_run_id     TEXT,
            source         TEXT        NOT NULL,
            group_number   INTEGER     NOT NULL,
            cycle          INTEGER     NOT NULL,
            batch_number   INTEGER,
            status         TEXT        NOT NULL,
            rows_received  INTEGER     NOT NULL DEFAULT 0,
            rows_inserted  INTEGER     NOT NULL DEFAULT 0,
            requested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

    def count(self, table: str) -> int:
        return int(self.hook.get_first(f"SELECT count(*) FROM {table};")[0])

    def current_cycle(self, source: str, group_number: int) -> int:
        fila = self.hook.get_first(
            f"SELECT COALESCE(MAX(cycle), 1) FROM {LOG_TABLE} WHERE source = %s AND group_number = %s;",
            parameters=(source, group_number),
        )
        return int(fila[0])

    def batches_in_cycle(self, source: str, group_number: int, cycle: int) -> set[int]:
        filas = self.hook.get_records(
            f"""SELECT DISTINCT batch_number FROM {LOG_TABLE}
                WHERE source = %s AND group_number = %s AND cycle = %s AND status = 'ok';""",
            parameters=(source, group_number, cycle),
        )
        return {int(f[0]) for f in filas}

    def log_request(
        self,
        *,
        dag_run_id: str,
        source: str,
        group_number: int,
        cycle: int,
        status: str,
        batch_number: int | None = None,
        rows_received: int = 0,
        rows_inserted: int = 0,
    ) -> None:
        self.hook.run(
            f"""INSERT INTO {LOG_TABLE}
                (dag_run_id, source, group_number, cycle, batch_number, status, rows_received, rows_inserted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
            parameters=(dag_run_id, source, group_number, cycle, batch_number, status,
                        rows_received, rows_inserted),
        )

    def insert_raw(self, rows: list[list[str]], *, source: str, cycle: int,
                   batch_number: int, dag_run_id: str) -> int:
        """Inserta las filas tal cual llegan"""
        valores = [
            (row_hash(fila), *fila, source, cycle, batch_number, dag_run_id)
            for fila in rows
            if len(fila) == len(RAW_COLUMNS) # para no insertar dato inválidos
        ]
        if not valores:
            return 0

        columnas = ", ".join(["row_hash", *RAW_COLUMNS, "source", "cycle", "batch_number", "dag_run_id"])
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                insertadas = execute_values(
                    cur,
                    f"INSERT INTO {RAW_TABLE} ({columnas}) VALUES %s "
                    "ON CONFLICT (row_hash) DO NOTHING RETURNING row_hash",
                    valores,
                    page_size=1000,
                    fetch=True,
                )
            conn.commit()
        finally:
            conn.close()
        return len(insertadas)

    def read_unprocessed_raw(self) -> pd.DataFrame:
        columnas = ", ".join(["row_hash", *RAW_COLUMNS])
        return self._consultar(f"SELECT {columnas} FROM {RAW_TABLE} WHERE processed_at IS NULL;")

    def write_clean(self, df: pd.DataFrame, processed_hashes: list[str]) -> int:
        """Inserta las filas limpias y marca como procesadas"""
        columnas = ["row_hash", *CLEAN_COLUMNS]
        # NaN/NA -> None para que lleguen como NULL.
        valores = df[columnas].astype(object).where(df[columnas].notna(), None).values.tolist()

        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                insertadas = []
                if valores:
                    insertadas = execute_values(
                        cur,
                        f"INSERT INTO {CLEAN_TABLE} ({', '.join(columnas)}) VALUES %s "
                        "ON CONFLICT (row_hash) DO NOTHING RETURNING row_hash",
                        valores,
                        page_size=1000,
                        fetch=True,
                    )
                cur.execute(
                    f"UPDATE {RAW_TABLE} SET processed_at = now() WHERE row_hash = ANY(%s);",
                    (processed_hashes,),
                )
            conn.commit()
        finally:
            conn.close()
        return len(insertadas)

    def promote_to_training(self) -> int:
        """Pasa a la tabla de entrenamiento las filas limpias completas que aun no esten"""
        columnas = ", ".join(CLEAN_COLUMNS)
        no_nulos = " AND ".join(f"c.{col} IS NOT NULL" for col in CLEAN_COLUMNS)
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {TRAIN_TABLE} (row_hash, {columnas}, split)
                    SELECT c.row_hash, {", ".join(f"c.{col}" for col in CLEAN_COLUMNS)},
                           CASE WHEN (('x' || substr(c.row_hash, 1, 7))::bit(28)::int % 100) < {TRAIN_FRACTION}
                                THEN 'train' ELSE 'test' END
                    FROM {CLEAN_TABLE} c
                    LEFT JOIN {TRAIN_TABLE} t ON t.row_hash = c.row_hash
                    WHERE t.row_hash IS NULL AND {no_nulos};
                """) # convierte el hash en un número aleatorio entre 0 y 99 y manda más el 80% de las filas a train
                insertadas = cur.rowcount
            conn.commit()
        finally:
            conn.close()
        return insertadas

    def read_training(self) -> pd.DataFrame:
        columnas = ", ".join([*CLEAN_COLUMNS, "split"])
        df = self._consultar(f"SELECT {columnas} FROM {TRAIN_TABLE};")
        if df.empty:
            raise ValueError(f"La tabla '{TRAIN_TABLE}' esta vacia, no hay con que entrenar.")
        return df
