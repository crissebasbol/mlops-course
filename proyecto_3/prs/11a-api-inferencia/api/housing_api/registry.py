import os
from dataclasses import dataclass, field

REPORTED_METRICS = (
    "holdout_mape",
    "val_mape",
    "test_mape",
    "latency_p95_ms",
    "model_size_mb",
    "train_rows",
)


@dataclass(frozen=True)
class ModelRef:
    version: int
    run_id: str | None = None
    tags: dict = field(default_factory=dict)


class MlflowRegistry:
    """Acceso al registro de MLflow. Igual que Airflow: skops con los tipos confiables guardados
    en el MLmodel y descarga por el proxy de artefactos del servidor."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._client = None

    def client(self):
        if self._client is None:
            os.environ.setdefault("MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD", "false")
            from mlflow import MlflowClient

            self._client = MlflowClient()
        return self._client

    def resolve(self, alias: str) -> ModelRef | None:
        from mlflow.exceptions import MlflowException

        try:
            mv = self.client().get_model_version_by_alias(self.model_name, alias)
        except MlflowException as error:
            if getattr(error, "error_code", "") in (
                "RESOURCE_DOES_NOT_EXIST",
                "INVALID_PARAMETER_VALUE",
            ):
                return None
            raise
        return ModelRef(int(mv.version), mv.run_id, dict(mv.tags or {}))

    def load(self, ref: ModelRef):
        import mlflow.sklearn

        self.client()
        return mlflow.sklearn.load_model(f"models:/{self.model_name}/{ref.version}")

    def run_metrics(self, run_id: str | None) -> dict:
        if not run_id:
            return {}
        metrics = self.client().get_run(run_id).data.metrics
        return {name: metrics[name] for name in REPORTED_METRICS if name in metrics}

    def set_alias(self, alias: str, version: int) -> None:
        self.client().set_registered_model_alias(self.model_name, alias, str(version))

    def tag_version(self, version: int, key: str, value: str) -> None:
        self.client().set_model_version_tag(self.model_name, str(version), key, value)
