from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from errors import PreprocessingError
from model import PriceModel, get_model
from preprocessing import transform_features

app = FastAPI(
    title="Taller 6: Estimador de precio de vivienda",
    description="Preprocesamiento (limpieza, validación y transformación) y estimación de precio.",
    version="1.0.0",
)


class Vivienda(BaseModel):
    barrio: str = Field(examples=["  Chapinero "])
    area_m2: float = Field(examples=[80])
    habitaciones: int = Field(examples=[3])
    estrato: int = Field(examples=[4])


@app.exception_handler(PreprocessingError)
def preprocessing_error_handler(request: Request, exc: PreprocessingError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.to_dict()})


@app.get("/health")
def health() -> dict:
    return {"status": "ok2"}


@app.post("/preprocess")
def preprocess(vivienda: Vivienda) -> dict:
    return transform_features(**vivienda.model_dump())


@app.post("/predict")
def predict(vivienda: Vivienda, model: PriceModel = Depends(get_model)) -> dict:
    features = transform_features(**vivienda.model_dump())
    return {
        "features": features,
        "precio_estimado_cop": model.predict(features),
        "modelo": model.version,
    }
