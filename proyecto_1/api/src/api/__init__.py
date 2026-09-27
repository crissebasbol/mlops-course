import io
import json
import os
import re
from functools import lru_cache
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from minio import Minio
from minio.error import S3Error
from pydantic import BaseModel, Field

MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "models")
MODEL_CACHE_SIZE = int(os.environ.get("MODEL_CACHE_SIZE", "4"))

ModelType = Literal["rf", "gmm"]
MODEL_TYPES: tuple[str, ...] = ("rf", "gmm")
DEFAULT_MODEL_TYPE: ModelType = "rf"

VERSION_PATTERN = re.compile(r"^v(\d+)/metadata\.json$")

COVER_TYPES = {
    0: "Spruce/Fir",
    1: "Lodgepole Pine",
    2: "Ponderosa Pine",
    3: "Cottonwood/Willow",
    4: "Aspen",
    5: "Douglas-fir",
    6: "Krummholz",
}

minio_client = Minio(
    os.environ.get("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.environ.get("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.environ.get("MINIO_SECRET_KEY", "admin123"),
    secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
)

def _read_object(name: str) -> bytes:
    respuesta = minio_client.get_object(MINIO_BUCKET, name)
    try:
        return respuesta.read()
    finally:
        respuesta.close()
        respuesta.release_conn()


def list_versions(model_type: str) -> list[int]:
    """Versiones completas (con metadata.json) de un tipo de modelo."""
    if not minio_client.bucket_exists(MINIO_BUCKET):
        return []
    versions = []
    for obj in minio_client.list_objects(MINIO_BUCKET, prefix=f"{model_type}/", recursive=True):
        if m := VERSION_PATTERN.match(obj.object_name.removeprefix(f"{model_type}/")):
            versions.append(int(m.group(1)))
    return sorted(versions)


def resolve_version(model_type: str, version: int | None) -> int:
    """Resuelve la version a usar. 404 si no hay modelos o la version no existe."""
    versions = list_versions(model_type)
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"No hay modelos '{model_type}' disponibles todavia.",
        )
    if version is None:
        return max(versions)
    if version not in versions:
        raise HTTPException(
            status_code=404,
            detail=(
                f"La version v{version} del modelo '{model_type}' no existe. "
                f"Versiones disponibles: {[f'v{v}' for v in versions]}."
            ),
        )
    return version


def load_metadata(model_type: str, version: int) -> dict:
    return json.loads(_read_object(f"{model_type}/v{version}/metadata.json"))


@lru_cache(maxsize=MODEL_CACHE_SIZE)
def load_payload(model_type: str, version: int) -> dict:
    """Descarga y deserializa un modelo"""
    return joblib.load(io.BytesIO(_read_object(f"{model_type}/v{version}/model.pkl")))


app = FastAPI(
    title="Covertype Inference API",
    version="1.0.0",
    description="Predice el tipo de cobertura forestal usando modelos rf o gmm versionados en MinIO.",
)


class CovertypeInput(BaseModel):
    elevation: float = Field(..., examples=[2596], description="Elevacion (m)")
    aspect: float = Field(..., examples=[51], description="Orientacion (grados azimut)")
    slope: float = Field(..., examples=[3], description="Pendiente (grados)")
    horizontal_distance_to_hydrology: float = Field(..., examples=[258])
    vertical_distance_to_hydrology: float = Field(..., examples=[0])
    horizontal_distance_to_roadways: float = Field(..., examples=[510])
    hillshade_9am: float = Field(..., examples=[221], description="Indice 0-255")
    hillshade_noon: float = Field(..., examples=[232], description="Indice 0-255")
    hillshade_3pm: float = Field(..., examples=[148], description="Indice 0-255")
    horizontal_distance_to_fire_points: float = Field(..., examples=[6279])
    wilderness_area: Literal["Rawah", "Neota", "Commanche", "Cache"] | None = Field(
        None, examples=["Rawah"], description="Area silvestre (requerida para 'rf')"
    )
    soil_type: str | None = Field(
        None, pattern=r"^C\d{4}$", examples=["C7745"], description="Codigo de suelo (requerido para 'rf')"
    )
    model_type: ModelType = Field(
        DEFAULT_MODEL_TYPE, description="Tipo de modelo: 'rf' o 'gmm'. Por defecto: 'rf'."
    )
    version: int | None = Field(
        None, description="Version del modelo (p.ej. 1, 2). Opcional; si se omite se usa la ultima."
    )


class PredictionOut(BaseModel):
    cover_type: int
    cover_type_name: str
    model_type: str
    version: int


@app.get("/health")
def health():
    try:
        bucket = minio_client.bucket_exists(MINIO_BUCKET)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MinIO no disponible: {exc}")
    return {"status": "ok", "minio_bucket": MINIO_BUCKET, "bucket_exists": bucket}


@app.get("/models")
def list_models():
    """Modelos disponibles agrupados por tipo con sus versiones y la ultima."""
    result = {}
    for model_type in MODEL_TYPES:
        versions = list_versions(model_type)
        result[model_type] = {
            "versions": [f"v{v}" for v in versions],
            "latest": f"v{max(versions)}" if versions else None,
        }
    return {"default_model_type": DEFAULT_MODEL_TYPE, "models": result}


@app.get("/models/{model_type}")
def model_details(model_type: ModelType):
    """Metadata (metricas, filas usadas, fecha) de cada version de un tipo de modelo."""
    versions = list_versions(model_type)
    return {
        "model_type": model_type,
        "latest": f"v{max(versions)}" if versions else None,
        "versions": [load_metadata(model_type, v) for v in versions],
    }


@app.get("/models/{model_type}/{version}")
def model_version_details(model_type: ModelType, version: int):
    version = resolve_version(model_type, version)
    return load_metadata(model_type, version)


def _predict_rf(payload: dict, features: CovertypeInput) -> int:
    if features.wilderness_area is None or features.soil_type is None:
        raise HTTPException(
            status_code=422,
            detail="El modelo 'rf' requiere los campos 'wilderness_area' y 'soil_type'.",
        )
    columnas = payload["numeric_features"] + payload["categorical_features"]
    X = pd.DataFrame([features.model_dump(include=set(columnas))])[columnas]
    return int(payload["pipeline"].predict(X)[0])


def _predict_gmm(payload: dict, features: CovertypeInput) -> int:
    columnas = payload["numeric_features"]
    X = pd.DataFrame([features.model_dump(include=set(columnas))])[columnas]
    cluster = int(payload["pipeline"].predict(X)[0])
    return int(payload["cluster_to_cover_type"][cluster])


@app.post("/predict", response_model=PredictionOut)
def predict(features: CovertypeInput):
    model_type = features.model_type
    version = resolve_version(model_type, features.version)
    try:
        payload = load_payload(model_type, version)
    except S3Error as exc:
        raise HTTPException(status_code=404, detail=f"No se pudo leer el modelo: {exc}")

    if model_type == "rf":
        cover_type = _predict_rf(payload, features)
    else:
        cover_type = _predict_gmm(payload, features)

    return PredictionOut(
        cover_type=cover_type,
        cover_type_name=COVER_TYPES.get(cover_type, "desconocido"),
        model_type=model_type,
        version=version,
    )
