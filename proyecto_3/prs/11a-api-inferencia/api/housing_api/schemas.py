from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from housing_ml.cleaning import MIN_PREV_SOLD_YEAR, RANGES

EXAMPLE = {
    "status": "for_sale",
    "bed": 3,
    "bath": 2,
    "acre_lot": 0.25,
    "house_size": 1800,
    "prev_sold_date": "2015-06-15",
    "city": "Springfield",
    "state": "Massachusetts",
    "zip_code": "01109",
    "brokered_by": "22611",
}


def _range(name: str) -> dict:
    low, high = RANGES[name]
    return {"ge": low, "le": high}


class PropertyFeatures(BaseModel):
    model_config = ConfigDict(
        extra="ignore", str_strip_whitespace=True, json_schema_extra={"examples": [EXAMPLE]}
    )

    status: str = Field(min_length=1)
    bed: float = Field(**_range("bed"))
    bath: float = Field(**_range("bath"))
    acre_lot: float = Field(**_range("acre_lot"))
    house_size: float = Field(**_range("house_size"))
    prev_sold_date: date | None = None
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip_code: str = Field(pattern=r"^\d{5}$")
    brokered_by: str | None = None

    @field_validator("zip_code", mode="before")
    @classmethod
    def _zip(cls, value: Any) -> Any:
        if isinstance(value, int | float) and not isinstance(value, bool) and value == int(value):
            return f"{int(value):05d}"
        return value

    @field_validator("brokered_by", mode="before")
    @classmethod
    def _broker(cls, value: Any) -> Any:
        if isinstance(value, int | float) and not isinstance(value, bool) and value == int(value):
            return str(int(value))
        return value

    @field_validator("prev_sold_date")
    @classmethod
    def _sold_date(cls, value: date | None) -> date | None:
        if value is not None and (value.year < MIN_PREV_SOLD_YEAR or value > date.today()):
            raise ValueError(f"debe estar entre {MIN_PREV_SOLD_YEAR} y hoy")
        return value


class PredictResponse(BaseModel):
    request_id: UUID
    predicted_price: float
    model_name: str
    model_version: int
    model_alias: str


class Contribution(BaseModel):
    feature: str
    value: Any
    shap_log: float
    effect_pct: float


class ExplainResponse(BaseModel):
    model_version: int
    predicted_price: float
    base_price: float
    contributions: list[Contribution]


class FeedbackRequest(BaseModel):
    request_id: UUID
    actual_price: float = Field(gt=0, le=RANGES["price"][1])


class RollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    actor: str = Field(default="api", min_length=1, max_length=100)


class ModelAction(BaseModel):
    action: str
    from_version: int | None
    to_version: int | None
    audit_logged: bool
