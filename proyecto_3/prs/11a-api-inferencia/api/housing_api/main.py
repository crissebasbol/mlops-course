import logging
import math
import re
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from housing_api.config import TRAFFIC_SOURCES, Settings
from housing_api.explain import Explainer, unknown_categories
from housing_api.inference_log import InferenceLogger, PostgresSink
from housing_api.metrics import (
    HTTP_DURATION,
    HTTP_IN_PROGRESS,
    HTTP_REQUESTS,
    INFERENCE_SECONDS,
    PREDICTION_ERRORS,
    PREDICTIONS,
    SHADOW_RELATIVE_DIFF,
    UNKNOWN_CATEGORY,
)
from housing_api.models import CHAMPION, SHADOW, LoadedModel, ModelManager
from housing_api.registry import MlflowRegistry
from housing_api.schemas import (
    ExplainResponse,
    FeedbackRequest,
    ModelAction,
    PredictResponse,
    PropertyFeatures,
    RollbackRequest,
)
from housing_ml.features import MODEL_INPUT_COLUMNS

log = logging.getLogger("housing_api")

ENDPOINTS = {
    "/predict",
    "/explain",
    "/feedback",
    "/model-info",
    "/admin/reload",
    "/admin/rollback",
    "/health",
    "/metrics",
}
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
REPLAY_ROW = re.compile(r"^[0-9a-f]{64}$")
NO_MODEL = "Todavía no hay modelo en producción: el alias champion no existe en MLflow."
DESCRIPTION = """
Predicción del precio de viviendas con el modelo `champion` del registro de MLflow.

- El modelo se recarga solo cuando cambia el alias, sin reiniciar la API.
- Si existe un `challenger` distinto, predice en sombra y se guarda junto al champion.
- Cada inferencia queda en `raw.inference_events` (header `X-Traffic-Source`).
"""


class HttpMetrics:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        endpoint = scope["path"] if scope["path"] in ENDPOINTS else "other"
        started = time.perf_counter()
        state = {"status": 500, "done": False}

        def finish() -> None:
            if not state["done"]:
                state["done"] = True
                HTTP_DURATION.labels(endpoint).observe(time.perf_counter() - started)
                HTTP_REQUESTS.labels(endpoint, str(state["status"])).inc()
                HTTP_IN_PROGRESS.labels(endpoint).dec()

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                finish()

        HTTP_IN_PROGRESS.labels(endpoint).inc()
        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            finish()


def to_frame(payload: PropertyFeatures) -> pd.DataFrame:
    record = payload.model_dump(mode="json")
    return pd.DataFrame([{name: record.get(name) for name in MODEL_INPUT_COLUMNS}])


def traffic_source(value: str | None) -> str:
    return value if value in TRAFFIC_SOURCES else "api"


def replay_row(value: str | None) -> str | None:
    return value if value and REPLAY_ROW.match(value) else None


def create_app(
    settings: Settings | None = None,
    registry=None,
    sink=None,
    explainer: Explainer | None = None,
    background: bool = True,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    settings = settings or Settings.from_env()
    registry = registry or MlflowRegistry(settings.model_name)
    sink = sink or PostgresSink(settings)
    explainer = explainer or Explainer()
    logger = InferenceLogger(sink, settings)

    def audit(action: str, before, after, actor: str, reason: str) -> bool:
        try:
            sink.write_action(action, before, after, actor, reason)
            return True
        except Exception:
            log.warning("No se registró la acción %s en audit.model_actions", action, exc_info=True)
            return False

    def on_change(result) -> None:
        audit(
            "reload",
            result.champion_before,
            result.champion_after,
            settings.instance,
            "La API detectó el cambio del alias champion y cargó el modelo sin reiniciar",
        )
        champion, _ = manager.snapshot()
        if champion is not None:
            try:
                explainer.warm(champion)
            except Exception:
                log.warning("No se pudo preparar SHAP para la v%s", champion.version, exc_info=True)

    manager = ModelManager(registry, settings, on_champion_change=on_change)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if background:
            manager.start()
            logger.start()
        yield
        if background:
            manager.stop()
            logger.stop()

    app = FastAPI(
        title="Housing price API",
        description=DESCRIPTION,
        version=settings.git_sha,
        lifespan=lifespan,
    )
    app.add_middleware(HttpMetrics)
    app.state.settings = settings
    app.state.manager = manager
    app.state.logger = logger
    app.state.registry = registry

    def base_event(source: str, request: dict | None, replay: str | None) -> dict:
        return {
            "request_id": str(uuid.uuid4()),
            "ts": datetime.now(UTC),
            "traffic_source": source,
            "endpoint": "/predict",
            "request": request,
            "model_name": settings.model_name,
            "replay_row_hash": replay_row(replay),
        }

    def after_prediction(
        event: dict, frame: pd.DataFrame, champion: LoadedModel, shadow: LoadedModel | None
    ) -> None:
        for field in unknown_categories(champion.model, frame):
            UNKNOWN_CATEGORY.labels(field).inc()
        if shadow is not None:
            started = time.perf_counter()
            try:
                value = float(shadow.model.predict(frame)[0])
                elapsed = time.perf_counter() - started
                INFERENCE_SECONDS.labels(SHADOW).observe(elapsed)
                PREDICTIONS.labels(SHADOW).inc()
                event.update(
                    shadow_version=shadow.version,
                    shadow_prediction=value,
                    shadow_latency_ms=elapsed * 1000,
                )
                SHADOW_RELATIVE_DIFF.observe(abs(value - event["prediction"]) / event["prediction"])
            except Exception:
                PREDICTION_ERRORS.labels("shadow_error").inc()
                log.warning("La sombra v%s no pudo predecir", shadow.version, exc_info=True)
        logger.log(event)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc: RequestValidationError):
        if request.url.path == "/predict":
            PREDICTION_ERRORS.labels("invalid_input").inc()
            body = exc.body if isinstance(exc.body, dict) else None
            errors = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
            )
            event = base_event(
                traffic_source(request.headers.get("x-traffic-source")),
                jsonable_encoder(body) if body is not None else None,
                request.headers.get("x-replay-row"),
            )
            logger.log({**event, "status_code": 422, "status": "invalid_input", "error": errors})
        return await request_validation_exception_handler(request, exc)

    @app.post("/predict", response_model=PredictResponse, tags=["inferencia"])
    def predict(
        payload: PropertyFeatures,
        tasks: BackgroundTasks,
        x_traffic_source: Annotated[str | None, Header()] = None,
        x_replay_row: Annotated[str | None, Header()] = None,
    ):
        event = base_event(
            traffic_source(x_traffic_source), payload.model_dump(mode="json"), x_replay_row
        )
        champion, shadow = manager.snapshot()
        if champion is None:
            PREDICTION_ERRORS.labels("no_model").inc()
            logger.log({**event, "status_code": 503, "status": "no_model", "error": NO_MODEL})
            raise HTTPException(503, NO_MODEL)
        frame = to_frame(payload)
        started = time.perf_counter()
        try:
            value = float(champion.model.predict(frame)[0])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"predicción inválida: {value}")
        except Exception as error:
            PREDICTION_ERRORS.labels("model_error").inc()
            logger.log(
                {
                    **event,
                    "status_code": 500,
                    "status": "error",
                    "error": str(error)[:500],
                    "champion_version": champion.version,
                }
            )
            raise HTTPException(500, "El modelo no pudo predecir") from error
        elapsed = time.perf_counter() - started
        INFERENCE_SECONDS.labels(CHAMPION).observe(elapsed)
        PREDICTIONS.labels(CHAMPION).inc()
        event.update(
            status_code=200,
            status="ok",
            champion_version=champion.version,
            prediction=value,
            champion_latency_ms=elapsed * 1000,
        )
        tasks.add_task(after_prediction, event, frame, champion, shadow)
        return PredictResponse(
            request_id=event["request_id"],
            predicted_price=value,
            model_name=settings.model_name,
            model_version=champion.version,
            model_alias=champion.alias,
        )

    @app.post("/explain", response_model=ExplainResponse, tags=["inferencia"])
    def explain(payload: PropertyFeatures):
        champion, _ = manager.snapshot()
        if champion is None:
            raise HTTPException(503, NO_MODEL)
        try:
            return explainer.explain(champion, to_frame(payload))
        except Exception as error:
            PREDICTION_ERRORS.labels("explain_error").inc()
            log.warning("No se pudo explicar con la v%s", champion.version, exc_info=True)
            raise HTTPException(500, "No se pudo explicar la predicción") from error

    @app.post("/feedback", status_code=202, tags=["inferencia"])
    def feedback(body: FeedbackRequest, x_traffic_source: Annotated[str | None, Header()] = None):
        try:
            sink.write_feedback(
                str(body.request_id), body.actual_price, traffic_source(x_traffic_source)
            )
        except Exception as error:
            log.warning("No se guardó el feedback", exc_info=True)
            raise HTTPException(503, "No se pudo guardar el feedback") from error
        return {"status": "accepted", "request_id": str(body.request_id)}

    @app.get("/model-info", tags=["modelo"])
    def model_info():
        champion, shadow = manager.snapshot()
        return {
            "model_name": settings.model_name,
            "champion": champion.info() if champion else None,
            "shadow": shadow.info() if shadow else None,
            "reload_interval_seconds": settings.reload_interval_seconds,
            "instance": settings.instance,
            "git_sha": settings.git_sha,
        }

    bearer = HTTPBearer(auto_error=False)

    def require_admin(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        if not settings.admin_token:
            raise HTTPException(503, "Administración deshabilitada: falta API_ADMIN_TOKEN")
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode(), settings.admin_token.encode()
        ):
            raise HTTPException(401, "Token inválido", headers={"WWW-Authenticate": "Bearer"})

    @app.post(
        "/admin/reload",
        response_model=ModelAction,
        dependencies=[Depends(require_admin)],
        tags=["administración"],
    )
    def reload():
        result = manager.refresh()
        if result.errors and result.champion_after is None:
            raise HTTPException(503, "; ".join(result.errors))
        logged = audit(
            "reload",
            result.champion_before,
            result.champion_after,
            "admin",
            "Recarga forzada con /admin/reload",
        )
        return ModelAction(
            action="reload",
            from_version=result.champion_before,
            to_version=result.champion_after,
            audit_logged=logged,
        )

    @app.post(
        "/admin/rollback",
        response_model=ModelAction,
        dependencies=[Depends(require_admin)],
        tags=["administración"],
    )
    def rollback(body: RollbackRequest):
        try:
            current = registry.resolve(settings.champion_alias)
            previous = registry.resolve(settings.previous_alias)
        except Exception as error:
            raise HTTPException(503, f"MLflow no responde: {error}") from error
        if current is None or previous is None or previous.version == current.version:
            raise HTTPException(409, "No hay una versión anterior distinta a la cual volver")
        try:
            registry.set_alias(settings.champion_alias, previous.version)
            registry.set_alias(settings.previous_alias, current.version)
            registry.tag_version(
                current.version, "rolled_back", f"{datetime.now(UTC).isoformat()} {body.reason}"
            )
        except Exception as error:
            raise HTTPException(503, f"No se pudieron mover los alias: {error}") from error
        logged = audit("rollback", current.version, previous.version, body.actor, body.reason)
        manager.refresh()
        return ModelAction(
            action="rollback",
            from_version=current.version,
            to_version=previous.version,
            audit_logged=logged,
        )

    @app.get("/health", tags=["operación"])
    def health():
        champion, shadow = manager.snapshot()
        return {
            "status": "ok",
            "model_loaded": champion is not None,
            "champion_version": champion and champion.version,
            "shadow_version": shadow and shadow.version,
        }

    @app.get("/metrics", tags=["operación"])
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
