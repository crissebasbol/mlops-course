from typing import Literal

from pydantic import BaseModel, Field

# Mismos vocabularios que airflow/dags/diabetes/config.py (tabla clean.diabetes).
AgeBin = Literal[
    "[0-10)", "[10-20)", "[20-30)", "[30-40)", "[40-50)",
    "[50-60)", "[60-70)", "[70-80)", "[80-90)", "[90-100)",
]
DiagGroup = Literal[
    "Circulatory", "Respiratory", "Digestive", "Diabetes", "Injury",
    "Musculoskeletal", "Genitourinary", "Neoplasms", "Other", "Unknown",
]
Med = Literal["No", "Steady", "Up", "Down"]

CLASS_LABELS = {0: "NO", 1: ">30", 2: "<30"}
CLASS_NAMES = {0: "no_readmission", 1: "late_readmission", 2: "early_readmission"}
CLASS_DESCRIPTIONS = {
    0: "No readmision",
    1: "Readmision tardia (mas de 30 dias)",
    2: "Readmision temprana (menos de 30 dias)",
}


class PatientInput(BaseModel):
    race: Literal["Caucasian", "AfricanAmerican", "Hispanic", "Asian", "Other", "Unknown"] = Field(..., examples=["Caucasian"])
    gender: Literal["Female", "Male"] = Field(..., examples=["Female"])
    age: AgeBin = Field(..., examples=["[70-80)"])
    admission_type: Literal["Emergency", "Urgent", "Elective", "Other", "Unknown"] = Field(..., examples=["Emergency"])
    discharge_disposition: Literal["Home", "Home health", "Transfer", "Other", "Unknown"] = Field(..., examples=["Home"])
    admission_source: Literal["Emergency", "Referral", "Transfer", "Other", "Unknown"] = Field(..., examples=["Emergency"])
    medical_specialty: Literal[
        "InternalMedicine", "Emergency/Trauma", "Family/GeneralPractice", "Cardiology",
        "Surgery-General", "Nephrology", "Orthopedics", "Orthopedics-Reconstructive",
        "Radiologist", "Other", "Unknown",
    ] = Field(..., examples=["InternalMedicine"])
    time_in_hospital: int = Field(..., ge=1, le=14, examples=[5], description="Dias de hospitalizacion (1-14)")
    num_lab_procedures: int = Field(..., ge=0, le=200, examples=[45])
    num_procedures: int = Field(..., ge=0, le=20, examples=[1])
    num_medications: int = Field(..., ge=0, le=150, examples=[16])
    number_outpatient: int = Field(..., ge=0, le=100, examples=[0])
    number_emergency: int = Field(..., ge=0, le=100, examples=[0])
    number_inpatient: int = Field(..., ge=0, le=50, examples=[1])
    number_diagnoses: int = Field(..., ge=1, le=20, examples=[9])
    diabetes_meds_active: int = Field(..., ge=0, le=23, examples=[2], description="Medicamentos para diabetes activos")
    diabetes_meds_changed: int = Field(..., ge=0, le=23, examples=[1], description="Medicamentos con cambio de dosis")
    diag_1_group: DiagGroup = Field(..., examples=["Circulatory"])
    diag_2_group: DiagGroup = Field(..., examples=["Diabetes"])
    diag_3_group: DiagGroup = Field(..., examples=["Circulatory"])
    max_glu_serum: Literal["None", "Norm", ">200", ">300"] = Field(..., examples=["None"])
    a1cresult: Literal["None", "Norm", ">7", ">8"] = Field(..., examples=[">8"])
    metformin: Med = Field(..., examples=["Steady"])
    glipizide: Med = Field(..., examples=["No"])
    glyburide: Med = Field(..., examples=["No"])
    pioglitazone: Med = Field(..., examples=["No"])
    rosiglitazone: Med = Field(..., examples=["No"])
    glimepiride: Med = Field(..., examples=["No"])
    insulin: Med = Field(..., examples=["Up"])
    change: Literal["No", "Ch"] = Field(..., examples=["Ch"])
    diabetesmed: Literal["No", "Yes"] = Field(..., examples=["Yes"])


class PredictionOut(BaseModel):
    request_id: str
    prediction: int
    prediction_label: str
    prediction_name: str
    prediction_description: str
    probability: float
    probabilities: dict[str, float]
    model_name: str
    model_version: int
    model_alias: str
    latency_ms: float
    replica: str
