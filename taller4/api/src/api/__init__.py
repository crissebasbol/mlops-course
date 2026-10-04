import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from pydantic import BaseModel, Field

MODEL_NAME = os.environ.get("MODEL_NAME", "covertype_rf")
MODEL_ALIAS = os.environ.get("MODEL_ALIAS", "champion")
MODEL_CACHE_SIZE = int(os.environ.get("MODEL_CACHE_SIZE", "4"))

NUMERIC_FEATURES = [
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
]
CATEGORICAL_FEATURES = ["wilderness_area", "soil_type"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

COVER_TYPES = {
    0: "Spruce/Fir",
    1: "Lodgepole Pine",
    2: "Ponderosa Pine",
    3: "Cottonwood/Willow",
    4: "Aspen",
    5: "Douglas-fir",
    6: "Krummholz",
}

client = MlflowClient()


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detail)


def aliases_by_version() -> dict[int, list[str]]:
    try:
        aliases = client.get_registered_model(MODEL_NAME).aliases
    except MlflowException:
        raise _not_found(f"El modelo '{MODEL_NAME}' no esta registrado en MLflow todavia.")
    result: dict[int, list[str]] = {}
    for alias, version in aliases.items():
        result.setdefault(int(version), []).append(alias)
    return result


def list_versions() -> list[int]:
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    return sorted(int(mv.version) for mv in versions)


def resolve_version(version: int | None) -> int:
    """Version pedida o, si no se indica, la que apunta el alias. 404 si no existe."""
    if version is None:
        try:
            return int(client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS).version)
        except MlflowException:
            raise _not_found(
                f"El modelo '{MODEL_NAME}' no tiene el alias '{MODEL_ALIAS}'. "
                "Corre el notebook de entrenamiento o indica una version."
            )
    versions = list_versions()
    if version not in versions:
        raise _not_found(
            f"La version {version} del modelo '{MODEL_NAME}' no existe. "
            f"Versiones disponibles: {versions}."
        )
    return version


def version_info(version: int, aliases: dict[int, list[str]]) -> dict:
    mv = client.get_model_version(MODEL_NAME, str(version))
    run = client.get_run(mv.run_id)
    return {
        "version": version,
        "aliases": aliases.get(version, []),
        "run_id": mv.run_id,
        "run_name": run.info.run_name,
        "status": mv.status,
        "description": mv.description,
        "created_at": datetime.fromtimestamp(mv.creation_timestamp / 1000, tz=timezone.utc).isoformat(),
        "params": run.data.params,
        "metrics": run.data.metrics,
    }


@lru_cache(maxsize=MODEL_CACHE_SIZE)
def load_model(version: int):
    """Descarga el modelo desde MLflow. Una version nunca cambia, por eso se guarda en memoria."""
    return mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")


app = FastAPI(
    title="Covertype Inference API (MLflow)",
    version="1.0.0",
    description=(
        f"Predice el tipo de cobertura forestal con el modelo '{MODEL_NAME}' del Model Registry de MLflow. "
        f"Por defecto usa la version con el alias '{MODEL_ALIAS}'."
    ),
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
    wilderness_area: Literal["Rawah", "Neota", "Commanche", "Cache"] = Field(
        ..., examples=["Rawah"], description="Area silvestre"
    )
    soil_type: str = Field(..., pattern=r"^C\d{4}$", examples=["C7745"], description="Codigo de suelo")
    version: int | None = Field(
        None, description=f"Version del modelo. Opcional; si se omite se usa el alias '{MODEL_ALIAS}'."
    )


class PredictionOut(BaseModel):
    cover_type: int
    cover_type_name: str
    model_name: str
    version: int
    alias: str | None


@app.get("/health")
def health():
    try:
        client.search_registered_models(max_results=1)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MLflow no disponible: {exc}")
    return {"status": "ok", "tracking_uri": mlflow.get_tracking_uri(), "model_name": MODEL_NAME}


@app.get("/models")
def list_models():
    """Versiones registradas del modelo, con sus alias, parametros y metricas."""
    aliases = aliases_by_version()
    return {
        "model_name": MODEL_NAME,
        "default_alias": MODEL_ALIAS,
        "aliases": {alias: version for version, names in aliases.items() for alias in names},
        "versions": [version_info(v, aliases) for v in list_versions()],
    }


@app.get("/models/{version}")
def model_version_details(version: int):
    aliases = aliases_by_version()
    return version_info(resolve_version(version), aliases)


@app.post("/predict", response_model=PredictionOut)
def predict(features: CovertypeInput):
    version = resolve_version(features.version)
    try:
        model = load_model(version)
    except MlflowException as exc:
        raise _not_found(f"No se pudo cargar el modelo desde MLflow: {exc}")

    X = pd.DataFrame([features.model_dump(include=set(FEATURES))])[FEATURES]
    X = X.astype({c: "object" for c in CATEGORICAL_FEATURES})
    cover_type = int(model.predict(X)[0])

    return PredictionOut(
        cover_type=cover_type,
        cover_type_name=COVER_TYPES.get(cover_type, "desconocido"),
        model_name=MODEL_NAME,
        version=version,
        alias=MODEL_ALIAS if features.version is None else None,
    )
