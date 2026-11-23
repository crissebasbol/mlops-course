import os
import socket
from dataclasses import dataclass

TRAFFIC_SOURCES = ("api", "streamlit", "locust", "replay")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    model_name: str = "housing-price-model"
    champion_alias: str = "champion"
    challenger_alias: str = "challenger"
    previous_alias: str = "previous_champion"
    reload_interval_seconds: float = 30.0
    shadow_enabled: bool = True
    admin_token: str = ""
    db_host: str = "postgres-data"
    db_port: int = 5432
    db_name: str = "housing"
    db_user: str = "api_writer"
    db_password: str = ""
    log_queue_size: int = 10_000
    log_batch_size: int = 500
    log_flush_seconds: float = 1.0
    instance: str = "api"
    git_sha: str = "unknown"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model_name=_env("MODEL_NAME", cls.model_name),
            reload_interval_seconds=float(_env("RELOAD_INTERVAL_SECONDS", "30")),
            shadow_enabled=_env("SHADOW_ENABLED", "true").lower() == "true",
            admin_token=_env("API_ADMIN_TOKEN", ""),
            db_host=_env("DATA_DB_HOST", cls.db_host),
            db_port=int(_env("DATA_DB_PORT", "5432")),
            db_name=_env("DATA_DB_NAME", cls.db_name),
            db_user=_env("DATA_DB_USER", cls.db_user),
            db_password=_env("DATA_DB_PASSWORD", ""),
            log_batch_size=int(_env("INFERENCE_LOG_BATCH_SIZE", "500")),
            log_flush_seconds=float(_env("INFERENCE_LOG_FLUSH_SECONDS", "1")),
            instance=_env("HOSTNAME", socket.gethostname()),
            git_sha=_env("GIT_SHA", "unknown"),
        )
