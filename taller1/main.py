"""
Servidor con FastAPI

Expone dos modelos entrenados:
  - random_forest: clasificador supervisado (modelo1/random_forest.pkl)
  - gmm: clustering no supervisado (modelo 2/penguin_gmm.pkl)
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
RF_PATH = BASE / "modelo1" / "random_forest.pkl"
GMM_PATH = BASE / "modelo 2" / "penguin_gmm.pkl"

DEFAULT_MODEL = "random_forest"

ISLAND_MAP = {"Biscoe": 0, "Dream": 1, "Torgersen": 2}
SEX_MAP = {"female": 0, "male": 1}
SPECIES_DECODE = {0: "Adelie", 1: "Chinstrap", 2: "Gentoo"}

registry: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if RF_PATH.exists():
        registry["random_forest"] = {
            "model": joblib.load(RF_PATH),
            "kind": "classifier",
            "description": "Random Forest Classifier (supervisado)",
        }
    if GMM_PATH.exists():
        gmm_data = joblib.load(GMM_PATH)
        registry["gmm"] = {
            "model": gmm_data["pipeline"],
            "cluster_to_species": gmm_data["cluster_to_species"],
            "kind": "clustering",
            "description": "Gaussian Mixture Model (no supervisado)",
        }
    if not registry:
        raise RuntimeError("No se encontraron modelos")
    yield
    registry.clear()


app = FastAPI(
    title="Penguin Species Inference API",
    version="1.0.0",
    description="Predice la especie de un pinguino usando Random Forest o GMM.",
    lifespan=lifespan,
)


class PenguinInput(BaseModel):
    bill_length_mm: float = Field(..., example=39.1, description="Longitud del pico (mm)")
    bill_depth_mm: float = Field(..., example=18.7, description="Profundidad del pico (mm)")
    flipper_length_mm: float = Field(..., example=181.0, description="Longitud de la aleta (mm)")
    body_mass_g: float = Field(..., example=3750.0, description="Masa corporal (g)")
    island: Literal["Biscoe", "Dream", "Torgersen"] | None = Field(
        None, description="Isla de observacion (requerida para random_forest)"
    )
    sex: Literal["female", "male"] | None = Field(
        None, description="Sexo del pinguino (requerido para random_forest)"
    )
    model_name: str | None = Field(
        None, description="Modelo a usar: 'random_forest' o 'gmm'. Por defecto: 'random_forest'"
    )


class PredictionOut(BaseModel):
    species: str
    model_used: str


@app.get("/health")
def health():
    return {"status": "ok", "default_model": DEFAULT_MODEL}


@app.get("/models")
def list_models():
    return {
        "default_model": DEFAULT_MODEL,
        "available": {name: info["description"] for name, info in registry.items()},
    }


@app.post("/predict", response_model=PredictionOut)
def predict(features: PenguinInput):
    name = features.model_name or DEFAULT_MODEL
    if name not in registry:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo '{name}' no disponible. Opciones: {list(registry.keys())}",
        )
    info = registry[name]

    if info["kind"] == "classifier":
        if features.island is None or features.sex is None:
            raise HTTPException(
                status_code=422,
                detail="El modelo 'random_forest' requiere los campos 'island' y 'sex'.",
            )
        X = np.array([[
            features.bill_length_mm,
            features.bill_depth_mm,
            features.flipper_length_mm,
            features.body_mass_g,
            ISLAND_MAP[features.island],
            SEX_MAP[features.sex],
        ]])
        pred = SPECIES_DECODE[int(info["model"].predict(X)[0])]

    elif info["kind"] == "clustering":
        X = np.array([[
            features.bill_length_mm,
            features.bill_depth_mm,
            features.flipper_length_mm,
            features.body_mass_g,
        ]])
        cluster = int(info["model"].predict(X)[0])
        pred = info["cluster_to_species"][cluster]

    else:
        raise HTTPException(status_code=500, detail="Tipo de modelo desconocido")

    return PredictionOut(species=pred, model_used=name)
