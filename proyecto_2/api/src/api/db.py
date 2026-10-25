import os

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

CONNINFO = (
    f"host={os.environ.get('DATA_DB_HOST', 'postgres-data')} "
    f"port={os.environ.get('DATA_DB_PORT', '5432')} "
    f"dbname={os.environ.get('DATA_DB_NAME', 'diabetes')} "
    f"user={os.environ.get('DATA_DB_USER', 'api_writer')} "
    f"password={os.environ.get('DATA_DB_PASSWORD', 'api_writer123')}"
)

pool = ConnectionPool(
    CONNINFO,
    min_size=1,
    max_size=int(os.environ.get("DB_POOL_MAX", "10")),
    open=False,
)

INSERT = """
INSERT INTO inference.predictions (
    request_id, input, prediction, prediction_label, probability, probabilities,
    model_name, model_version, model_alias, latency_ms, api_replica
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def log_prediction(row: dict) -> None:
    with pool.connection() as conn:
        conn.execute(INSERT, (
            row["request_id"], Jsonb(row["input"]), row["prediction"], row["prediction_label"],
            row["probability"], Jsonb(row["probabilities"]), row["model_name"], row["model_version"],
            row["model_alias"], row["latency_ms"], row["replica"],
        ))


def is_alive() -> bool:
    try:
        with pool.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
