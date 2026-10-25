import logging
import threading
from datetime import datetime, timezone

import mlflow.sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from .metrics import MODEL_INFO, MODEL_RELOADS

log = logging.getLogger("api.model")


class ModelStore:
    """Modelo `name@alias` en memoria.

    Se carga al arrancar y un hilo revisa el alias cada `refresh_seconds`; solo
    descarga de MLflow cuando la version del alias cambio. /predict nunca llama
    a MLflow.
    """

    def __init__(self, name: str, alias: str, refresh_seconds: int):
        self.name = name
        self.alias = alias
        self.refresh_seconds = refresh_seconds
        self.client = MlflowClient()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.model = None
        self.info: dict = {}

    def refresh(self) -> bool:
        try:
            mv = self.client.get_model_version_by_alias(self.name, self.alias)
        except MlflowException as exc:
            log.warning("Sin modelo %s@%s en MLflow todavia: %s", self.name, self.alias, exc)
            return False

        version = int(mv.version)
        if version == self.info.get("version"):
            return False

        model = mlflow.sklearn.load_model(f"models:/{self.name}/{version}")
        run = self.client.get_run(mv.run_id)
        info = {
            "model_name": self.name,
            "alias": self.alias,
            "version": version,
            "run_id": mv.run_id,
            "run_name": run.info.run_name,
            "model_type": mv.tags.get("model_type", run.data.tags.get("model_type")),
            "metrics": {k: v for k, v in run.data.metrics.items() if k.startswith(("val_", "test_"))},
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            previous = self.info.get("version")
            self.model, self.info = model, info

        if previous is not None:
            MODEL_INFO.remove(self.name, str(previous), self.alias)
        MODEL_INFO.labels(self.name, str(version), self.alias).set(1)
        MODEL_RELOADS.inc()
        log.info("Modelo cargado: %s v%s (antes v%s)", self.name, version, previous)
        return True

    def current(self):
        with self._lock:
            return self.model, dict(self.info)

    def _loop(self) -> None:
        while not self._stop.wait(self.refresh_seconds):
            try:
                self.refresh()
            except Exception:
                log.exception("Fallo revisando el alias en MLflow")

    def start(self) -> None:
        try:
            self.refresh()
        except Exception:
            log.exception("No se pudo cargar el modelo al arrancar; se reintentara")
        self._thread = threading.Thread(target=self._loop, name="model-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
