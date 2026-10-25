import logging
import os
import socket
import time
import uuid
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import db
from .metrics import (
    HTTP_IN_PROGRESS,
    HTTP_LATENCY,
    HTTP_REQUESTS,
    INFERENCE_LATENCY,
    INFERENCE_LOG_LATENCY,
    PREDICTION_ERRORS,
    PREDICTIONS,
)
from .model_store import ModelStore
from .schemas import CLASS_DESCRIPTIONS, CLASS_LABELS, CLASS_NAMES, PatientInput, PredictionOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MODEL_NAME = os.environ.get("MODEL_NAME", "diabetes_readmission")
MODEL_ALIAS = os.environ.get("MODEL_ALIAS", "champion")
REFRESH_SECONDS = int(os.environ.get("MODEL_REFRESH_SECONDS", "60"))
REPLICA = socket.gethostname()

FEATURES = list(PatientInput.model_fields)

store = ModelStore(MODEL_NAME, MODEL_ALIAS, REFRESH_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.pool.open(wait=False)
    store.start()
    yield
    store.stop()
    db.pool.close()


app = FastAPI(
    title="Diabetes Readmission API (Proyecto 2)",
    version="1.0.0",
    description=(
        f"Predice la readmision hospitalaria (NO, >30, <30) con '{MODEL_NAME}@{MODEL_ALIAS}' "
        "del Model Registry de MLflow y registra cada inferencia en Postgres."
    ),
    lifespan=lifespan,
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    HTTP_IN_PROGRESS.inc()
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        endpoint = route.path if route else "unmatched"
        HTTP_LATENCY.labels(request.method, endpoint).observe(time.perf_counter() - start)
        HTTP_REQUESTS.labels(request.method, endpoint, str(status)).inc()
        HTTP_IN_PROGRESS.dec()


@app.get("/health")
def health():
    _, info = store.current()
    return {
        "status": "ok",
        "model_loaded": bool(info),
        "model_version": info.get("version"),
        "database": db.is_alive(),
        "replica": REPLICA,
    }


@app.get("/model-info")
def model_info():
    model, info = store.current()
    if model is None:
        return {
            "model_name": MODEL_NAME,
            "alias": MODEL_ALIAS,
            "status": "not_loaded",
            "detail": "Aun no hay un modelo con ese alias en MLflow. Ejecute el DAG diabetes_pipeline.",
            "replica": REPLICA,
        }
    return {**info, "status": "loaded", "refresh_seconds": REFRESH_SECONDS, "replica": REPLICA}


@app.post("/reload")
def reload_model():
    changed = store.refresh()
    _, info = store.current()
    return {"reloaded": changed, "version": info.get("version"), "replica": REPLICA}


@app.post("/predict", response_model=PredictionOut)
def predict(patient: PatientInput):
    model, info = store.current()
    if model is None:
        PREDICTION_ERRORS.labels("model_not_loaded").inc()
        raise HTTPException(status_code=503, detail="No hay modelo productivo cargado todavia")

    start = time.perf_counter()
    payload = patient.model_dump()
    with INFERENCE_LATENCY.time():
        proba = model.predict_proba(pd.DataFrame([payload])[FEATURES])[0]
    classes = [int(c) for c in model.classes_]
    best = int(proba.argmax())
    prediction = classes[best]
    latency_ms = (time.perf_counter() - start) * 1000

    result = PredictionOut(
        request_id=str(uuid.uuid4()),
        prediction=prediction,
        prediction_label=CLASS_LABELS[prediction],
        prediction_name=CLASS_NAMES[prediction],
        prediction_description=CLASS_DESCRIPTIONS[prediction],
        probability=round(float(proba[best]), 6),
        probabilities={CLASS_LABELS[c]: round(float(p), 6) for c, p in zip(classes, proba)},
        model_name=info["model_name"],
        model_version=info["version"],
        model_alias=info["alias"],
        latency_ms=round(latency_ms, 3),
        replica=REPLICA,
    )

    try:
        with INFERENCE_LOG_LATENCY.time():
            db.log_prediction({**result.model_dump(), "input": payload})
    except Exception as exc:
        PREDICTION_ERRORS.labels("inference_log").inc()
        logging.getLogger("api").exception("No se pudo registrar la inferencia")
        raise HTTPException(status_code=500, detail=f"No se pudo registrar la inferencia: {exc}") from exc

    PREDICTIONS.labels(result.prediction_label, str(result.model_version)).inc()
    return result


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
