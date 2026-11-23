import contextlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from housing_api.config import Settings
from housing_api.metrics import MODEL_INFO, MODEL_RELOAD_FAILURES, MODEL_RELOADS
from housing_api.registry import ModelRef

log = logging.getLogger(__name__)

CHAMPION = "champion"
SHADOW = "shadow"


@dataclass(frozen=True)
class LoadedModel:
    role: str
    alias: str
    version: int
    run_id: str | None
    model: Any
    loaded_at: datetime
    metrics: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)

    def as_role(self, role: str, alias: str) -> "LoadedModel":
        return LoadedModel(
            role,
            alias,
            self.version,
            self.run_id,
            self.model,
            self.loaded_at,
            self.metrics,
            self.tags,
        )

    def info(self) -> dict:
        return {
            "role": self.role,
            "alias": self.alias,
            "version": self.version,
            "run_id": self.run_id,
            "loaded_at": self.loaded_at.isoformat(),
            "metrics": self.metrics,
            "decision": self.tags.get("decision"),
            "ingestion_id": self.tags.get("ingestion_id"),
        }


@dataclass
class RefreshResult:
    champion_before: int | None
    champion_after: int | None
    shadow_before: int | None
    shadow_after: int | None
    errors: list[str] = field(default_factory=list)

    @property
    def champion_changed(self) -> bool:
        return self.champion_before != self.champion_after


class ModelManager:
    """Mantiene champion y sombra. Descarga fuera del lock y cambia ambos en un solo paso."""

    def __init__(self, registry, settings: Settings, on_champion_change=None):
        self.registry = registry
        self.settings = settings
        self.on_champion_change = on_champion_change
        self._lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._champion: LoadedModel | None = None
        self._shadow: LoadedModel | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> tuple[LoadedModel | None, LoadedModel | None]:
        with self._lock:
            return self._champion, self._shadow

    def _load(self, ref: ModelRef, role: str, alias: str) -> LoadedModel:
        model = self.registry.load(ref)
        try:
            metrics = self.registry.run_metrics(ref.run_id)
        except Exception:
            log.warning("Sin métricas del run %s", ref.run_id, exc_info=True)
            metrics = {}
        return LoadedModel(
            role, alias, ref.version, ref.run_id, model, datetime.now(UTC), metrics, ref.tags
        )

    def _reuse(self, version: int, *candidates: LoadedModel | None) -> LoadedModel | None:
        return next((c for c in candidates if c is not None and c.version == version), None)

    def refresh(self) -> RefreshResult:
        with self._refresh_lock:
            return self._refresh()

    def _refresh(self) -> RefreshResult:
        s = self.settings
        current_champion, current_shadow = self.snapshot()
        result = RefreshResult(
            current_champion and current_champion.version,
            current_champion and current_champion.version,
            current_shadow and current_shadow.version,
            current_shadow and current_shadow.version,
        )
        new_champion = current_champion
        try:
            ref = self.registry.resolve(s.champion_alias)
            if ref is None:
                new_champion = None
            elif current_champion is None or current_champion.version != ref.version:
                reused = self._reuse(ref.version, current_shadow)
                new_champion = (
                    reused.as_role(CHAMPION, s.champion_alias)
                    if reused
                    else self._load(ref, CHAMPION, s.champion_alias)
                )
        except Exception as error:
            MODEL_RELOAD_FAILURES.labels(CHAMPION).inc()
            result.errors.append(f"champion: {error}")
            log.warning("No se pudo actualizar el champion; sigue el anterior", exc_info=True)

        new_shadow = current_shadow
        try:
            ref = self.registry.resolve(s.challenger_alias) if s.shadow_enabled else None
            if ref is None or (new_champion is not None and ref.version == new_champion.version):
                new_shadow = None
            elif current_shadow is None or current_shadow.version != ref.version:
                reused = self._reuse(ref.version, current_champion)
                new_shadow = (
                    reused.as_role(SHADOW, s.challenger_alias)
                    if reused
                    else self._load(ref, SHADOW, s.challenger_alias)
                )
        except Exception as error:
            MODEL_RELOAD_FAILURES.labels(SHADOW).inc()
            result.errors.append(f"shadow: {error}")
            log.warning("No se pudo actualizar la sombra", exc_info=True)
            new_shadow = None

        with self._lock:
            self._champion, self._shadow = new_champion, new_shadow
        result.champion_after = new_champion and new_champion.version
        result.shadow_after = new_shadow and new_shadow.version
        self._publish(current_champion, new_champion, CHAMPION)
        self._publish(current_shadow, new_shadow, SHADOW)
        if result.champion_changed:
            log.info("Champion: %s -> %s", result.champion_before, result.champion_after)
        return result

    def _publish(self, before: LoadedModel | None, after: LoadedModel | None, role: str) -> None:
        if before is after:
            return
        if before is not None:
            with contextlib.suppress(KeyError):
                MODEL_INFO.remove(str(before.version), before.alias, role)
        if after is not None:
            MODEL_INFO.labels(str(after.version), after.alias, role).set(1)
        if (before and before.version) != (after and after.version):
            MODEL_RELOADS.labels(role).inc()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="model-reload", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                result = self.refresh()
                if result.champion_changed and self.on_champion_change:
                    self.on_champion_change(result)
            except Exception:
                log.exception("Error inesperado al revisar los alias")
            self._stop.wait(self.settings.reload_interval_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
