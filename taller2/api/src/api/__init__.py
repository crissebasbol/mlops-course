"""
Servidor con FastAPI.

Expone los modelos entrenados por el notebook y guardados de forma versionada
en el almacenamiento compartido:

  - rf  (Random Forest y otros clasificadores supervisados) -> models/rf/vN.pkl
  - gmm (Gaussian Mixture, clustering no supervisado)        -> models/gmm/vN.pkl

La peticion de inferencia acepta el tipo de modelo y, opcionalmente, la
version. Si no se envia la version se usa la ultima disponible. Si la version
solicitada no existe se responde con un error 404 especifico.
"""

import os
import re
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Directorio raiz de los modelos versionados (montado desde shared_storage/models).
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/models"))

ModelType = Literal["rf", "gmm"]
MODEL_TYPES: tuple[str, ...] = ("rf", "gmm")
DEFAULT_MODEL_TYPE: ModelType = "rf"

VERSION_PATTERN = re.compile(r"^v(\d+)\.pkl$")

# Cache de payloads ya cargados: (model_type, version) -> payload.
_cache: dict[tuple[str, int], dict] = {}


def list_versions(model_type: str) -> list[int]:
    """Devuelve las versiones disponibles (enteros) para un tipo de modelo."""
    subdir = MODELS_DIR / model_type
    if not subdir.exists():
        return []
    versions = [
        int(m.group(1))
        for f in subdir.iterdir()
        if (m := VERSION_PATTERN.match(f.name))
    ]
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


def load_payload(model_type: str, version: int) -> dict:
    """Carga (con cache) el payload de un modelo/version desde disco."""
    key = (model_type, version)
    if key not in _cache:
        path = MODELS_DIR / model_type / f"v{version}.pkl"
        _cache[key] = joblib.load(path)
    return _cache[key]


app = FastAPI(
    title="Penguin Species Inference API",
    version="2.0.0",
    description="Predice la especie de un pinguino usando modelos rf o gmm versionados.",
)


class PenguinInput(BaseModel):
    bill_length_mm: float = Field(..., example=39.1, description="Longitud del pico (mm)")
    bill_depth_mm: float = Field(..., example=18.7, description="Profundidad del pico (mm)")
    flipper_length_mm: float = Field(..., example=181.0, description="Longitud de la aleta (mm)")
    body_mass_g: float = Field(..., example=3750.0, description="Masa corporal (g)")
    island: Literal["Biscoe", "Dream", "Torgersen"] | None = Field(
        None, description="Isla de observacion (requerida para 'rf')"
    )
    sex: Literal["female", "male"] | None = Field(
        None, description="Sexo del pinguino (requerido para 'rf')"
    )
    model_type: ModelType = Field(
        DEFAULT_MODEL_TYPE, description="Tipo de modelo: 'rf' o 'gmm'. Por defecto: 'rf'."
    )
    version: int | None = Field(
        None,
        description="Version del modelo (p.ej. 1, 2). Opcional; si se omite se usa la ultima.",
    )


class PredictionOut(BaseModel):
    species: str
    model_type: str
    version: int


@app.get("/health")
def health():
    return {"status": "ok", "default_model_type": DEFAULT_MODEL_TYPE}


@app.get("/models")
def list_models():
    """Lista los modelos disponibles agrupados por tipo con sus versiones."""
    result = {}
    for model_type in MODEL_TYPES:
        versions = list_versions(model_type)
        result[model_type] = {
            "versions": [f"v{v}" for v in versions],
            "latest": f"v{max(versions)}" if versions else None,
        }
    return {"default_model_type": DEFAULT_MODEL_TYPE, "models": result}


def _predict_rf(payload: dict, features: PenguinInput) -> str:
    if features.island is None or features.sex is None:
        raise HTTPException(
            status_code=422,
            detail="El modelo 'rf' requiere los campos 'island' y 'sex'.",
        )

    encoders = payload["encoders"]
    metadata = payload["metadata"]
    model = payload["models"][metadata["default_model"]]

    island_enc = int(encoders["island"].transform([features.island])[0])
    sex_enc = int(encoders["sex"].transform([features.sex])[0])

    # Orden segun metadata["feature_columns"]: numericas + categoricas.
    X = np.array([[
        features.bill_length_mm,
        features.bill_depth_mm,
        features.flipper_length_mm,
        features.body_mass_g,
        island_enc,
        sex_enc,
    ]])
    pred = int(model.predict(X)[0])
    return str(encoders["species"].inverse_transform([pred])[0])


def _predict_gmm(payload: dict, features: PenguinInput) -> str:
    pipeline = payload["pipeline"]
    cluster_to_species = payload["cluster_to_species"]
    if cluster_to_species is None:
        raise HTTPException(
            status_code=500,
            detail="El modelo 'gmm' no tiene mapeo cluster -> especie.",
        )

    X = np.array([[
        features.bill_length_mm,
        features.bill_depth_mm,
        features.flipper_length_mm,
        features.body_mass_g,
    ]])
    cluster = int(pipeline.predict(X)[0])
    return str(cluster_to_species[cluster])


@app.post("/predict", response_model=PredictionOut)
def predict(features: PenguinInput):
    model_type = features.model_type
    version = resolve_version(model_type, features.version)
    payload = load_payload(model_type, version)

    if model_type == "rf":
        species = _predict_rf(payload, features)
    else:
        species = _predict_gmm(payload, features)

    return PredictionOut(species=species, model_type=model_type, version=version)
