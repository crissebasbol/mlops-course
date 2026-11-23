import logging
import queue
import threading
import time

from housing_api.config import Settings
from housing_api.metrics import INFERENCE_LOG_ERRORS, INFERENCE_LOG_QUEUE, INFERENCE_LOG_SECONDS

log = logging.getLogger(__name__)

EVENT_COLUMNS = (
    "request_id",
    "ts",
    "traffic_source",
    "endpoint",
    "request",
    "status_code",
    "status",
    "error",
    "model_name",
    "champion_version",
    "prediction",
    "champion_latency_ms",
    "shadow_version",
    "shadow_prediction",
    "shadow_latency_ms",
    "replay_row_hash",
)


class PostgresSink:
    """Escribe con el rol api_writer: solo INSERT en eventos, feedback y acciones."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._conn = None

    def _connect(self):
        import psycopg2

        s = self.settings
        return psycopg2.connect(
            host=s.db_host,
            port=s.db_port,
            dbname=s.db_name,
            user=s.db_user,
            password=s.db_password,
            connect_timeout=5,
            application_name=f"housing-api-{s.instance}",
        )

    def write_events(self, events: list[dict]) -> None:
        from psycopg2.extras import Json, execute_values

        rows = [
            tuple(Json(e.get(c)) if c == "request" else e.get(c) for c in EVENT_COLUMNS)
            for e in events
        ]
        try:
            if self._conn is None or self._conn.closed:
                self._conn = self._connect()
            with self._conn, self._conn.cursor() as cur:
                execute_values(
                    cur,
                    f"INSERT INTO raw.inference_events ({', '.join(EVENT_COLUMNS)}) VALUES %s",
                    rows,
                )
        except Exception:
            if self._conn is not None:
                self._conn.close()
            self._conn = None
            raise

    def _execute(self, sql: str, params: tuple) -> None:
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(sql, params)
        finally:
            conn.close()

    def write_feedback(self, request_id: str, actual_price: float, source: str) -> None:
        self._execute(
            "INSERT INTO raw.inference_feedback (request_id, actual_price, source) "
            "VALUES (%s, %s, %s)",
            (request_id, actual_price, source),
        )

    def write_action(
        self, action: str, from_version, to_version, actor: str, reason: str | None
    ) -> None:
        self._execute(
            "INSERT INTO audit.model_actions (action, from_version, to_version, actor, reason) "
            "VALUES (%s, %s, %s, %s, %s)",
            (action, from_version, to_version, actor, reason),
        )


class InferenceLogger:
    """Cola en memoria y escritura por lotes en un hilo: Postgres no suma latencia a /predict."""

    def __init__(self, sink, settings: Settings):
        self.sink = sink
        self.batch_size = settings.log_batch_size
        self.flush_seconds = settings.log_flush_seconds
        self._queue: queue.Queue = queue.Queue(maxsize=settings.log_queue_size)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def log(self, event: dict) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            INFERENCE_LOG_ERRORS.labels("queue_full").inc()
        INFERENCE_LOG_QUEUE.set(self._queue.qsize())

    def _take(self, timeout: float) -> list[dict]:
        batch = []
        try:
            batch.append(self._queue.get(timeout=timeout))
            while len(batch) < self.batch_size:
                batch.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        return batch

    def flush(self, timeout: float = 0.0) -> int:
        written = 0
        while batch := self._take(timeout):
            started = time.perf_counter()
            try:
                self.sink.write_events(batch)
                written += len(batch)
            except Exception:
                INFERENCE_LOG_ERRORS.labels("database").inc(len(batch))
                log.warning("No se guardaron %s eventos de inferencia", len(batch), exc_info=True)
            INFERENCE_LOG_SECONDS.observe(time.perf_counter() - started)
            INFERENCE_LOG_QUEUE.set(self._queue.qsize())
            timeout = 0.0
        return written

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="inference-log", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.flush(timeout=self.flush_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.flush()
