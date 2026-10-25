from contextlib import contextmanager

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from .config import DATA_DB, FEATURES, RAW_COLUMNS

CLEAN_COLUMNS = ["row_hash", "batch_id", "encounter_id", "patient_nbr", "split", *FEATURES, "readmitted", "target"]
REQUIRED_TABLES = ["raw.batches", "raw.diabetes", "clean.diabetes", "inference.predictions"]


class DiabetesDatabase:
    """Todo el SQL contra la base `diabetes` (schemas raw, clean e inference).
    Las tablas las crea database/init/02_tables.sql."""

    @contextmanager
    def cursor(self):
        conn = psycopg2.connect(**DATA_DB)
        try:
            with conn, conn.cursor() as cur:
                yield cur
        finally:
            conn.close()

    def query(self, sql: str, params=None) -> pd.DataFrame:
        with self.cursor() as cur:
            cur.execute(sql, params)
            columns = [d[0] for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=columns)

    def missing_tables(self) -> list[str]:
        with self.cursor() as cur:
            missing = []
            for table in REQUIRED_TABLES:
                cur.execute("SELECT to_regclass(%s)", (table,))
                if cur.fetchone()[0] is None:
                    missing.append(table)
            return missing

    def next_batch(self, total_batches: int) -> int | None:
        """Primer lote que no ha terminado (status distinto de processed)."""
        with self.cursor() as cur:
            cur.execute("SELECT batch_id FROM raw.batches WHERE status = 'processed'")
            done = {r[0] for r in cur.fetchall()}
        pending = [b for b in range(total_batches) if b not in done]
        return pending[0] if pending else None

    def start_batch(self, batch_id: int, row_start: int, row_end: int, source_file: str, run_id: str) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.batches (batch_id, source_file, row_start, row_end, status, dag_run_id)
                VALUES (%s, %s, %s, %s, 'loading', %s)
                ON CONFLICT (batch_id) DO UPDATE
                   SET status = 'loading', dag_run_id = EXCLUDED.dag_run_id, updated_at = now()
                """,
                (batch_id, source_file, row_start, row_end, run_id),
            )

    def update_batch(self, batch_id: int, **fields) -> None:
        assignments = ", ".join(f"{k} = %s" for k in fields)
        with self.cursor() as cur:
            cur.execute(
                f"UPDATE raw.batches SET {assignments}, updated_at = now() WHERE batch_id = %s",
                (*fields.values(), batch_id),
            )

    def insert_raw(self, df: pd.DataFrame, batch_id: int, source_file: str) -> int:
        """Inserta el lote crudo; las filas que ya existen (mismo row_hash) se ignoran."""
        columns = ["row_hash", "batch_id", "source_file", "source_row", *RAW_COLUMNS]
        rows = [
            (r.row_hash, batch_id, source_file, int(r.source_row), *[getattr(r, c) for c in RAW_COLUMNS])
            for r in df.itertuples(index=False)
        ]
        with self.cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO raw.diabetes ({', '.join(columns)}) VALUES %s ON CONFLICT (row_hash) DO NOTHING",
                rows,
                page_size=2000,
            )
            cur.execute("SELECT count(*) FROM raw.diabetes WHERE batch_id = %s", (batch_id,))
            return cur.fetchone()[0]

    def fetch_raw(self, batch_id: int, statuses: tuple[str, ...]) -> pd.DataFrame:
        return self.query(
            f"SELECT row_hash, batch_id, {', '.join(RAW_COLUMNS)} FROM raw.diabetes "
            "WHERE batch_id = %s AND status IN %s",
            (batch_id, statuses),
        )

    def set_raw_status(self, statuses: dict[str, tuple[str, str | None]]) -> None:
        """statuses: row_hash -> (status, motivo)."""
        if not statuses:
            return
        rows = [(h, s, r) for h, (s, r) in statuses.items()]
        with self.cursor() as cur:
            execute_values(
                cur,
                """
                UPDATE raw.diabetes AS t
                   SET status = v.status, status_reason = v.reason
                  FROM (VALUES %s) AS v(row_hash, status, reason)
                 WHERE t.row_hash = v.row_hash
                """,
                rows,
                page_size=2000,
            )

    def upsert_clean(self, df: pd.DataFrame) -> int:
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in CLEAN_COLUMNS if c != "row_hash")
        rows = [tuple(r) for r in df[CLEAN_COLUMNS].itertuples(index=False, name=None)]
        with self.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO clean.diabetes ({', '.join(CLEAN_COLUMNS)}) VALUES %s
                ON CONFLICT (row_hash) DO UPDATE SET {updates}, processed_at = now()
                """,
                rows,
                page_size=2000,
            )
        return len(rows)

    def fetch_clean(self) -> pd.DataFrame:
        return self.query(f"SELECT {', '.join(CLEAN_COLUMNS)} FROM clean.diabetes")
