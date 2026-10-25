import os

SOURCE_URL = os.environ.get(
    "SOURCE_URL",
    "https://drive.usercontent.google.com/download?id=1k5-1caezQ3zWJbKaiMULTGq-3sz6uThC&export=download&confirm=t",
)
SOURCE_FILE = os.environ.get("SOURCE_FILE", "Diabetes.csv")
DATASETS_BUCKET = os.environ.get("DATASETS_BUCKET", "datasets")
SOURCE_OBJECT = f"source/{SOURCE_FILE}"
SPLITS_PREFIX = "splits"

BATCH_SIZE = min(int(os.environ.get("BATCH_SIZE", "15000")), 15000)
MAX_REJECTED_PCT = float(os.environ.get("MAX_REJECTED_PCT", "5"))
TRAIN_PCT = 70
VAL_PCT = 15
RANDOM_STATE = 42

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "admin123")

DATA_DB = {
    "host": os.environ.get("DATA_DB_HOST", "postgres-data"),
    "port": int(os.environ.get("DATA_DB_PORT", "5432")),
    "dbname": os.environ.get("DATA_DB_NAME", "diabetes"),
    "user": os.environ.get("DATA_DB_USER", "airflow_etl"),
    "password": os.environ.get("DATA_DB_PASSWORD", "airflow_etl123"),
}

MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "diabetes_readmission")
MODEL_NAME = os.environ.get("MODEL_NAME", "diabetes_readmission")
CHAMPION_ALIAS = "champion"
CHALLENGER_ALIAS = "challenger"
SELECTION_METRIC = "val_f1_macro"
MODEL_TYPES = ["logistic_regression", "random_forest", "hist_gradient_boosting"]
MIN_IMPROVEMENT = float(os.environ.get("MIN_IMPROVEMENT", "0.0"))

SOURCE_COLUMNS = [
    "encounter_id", "patient_nbr", "race", "gender", "age", "weight",
    "admission_type_id", "discharge_disposition_id", "admission_source_id",
    "time_in_hospital", "payer_code", "medical_specialty", "num_lab_procedures",
    "num_procedures", "num_medications", "number_outpatient", "number_emergency",
    "number_inpatient", "diag_1", "diag_2", "diag_3", "number_diagnoses",
    "max_glu_serum", "A1Cresult", "metformin", "repaglinide", "nateglinide",
    "chlorpropamide", "glimepiride", "acetohexamide", "glipizide", "glyburide",
    "tolbutamide", "pioglitazone", "rosiglitazone", "acarbose", "miglitol",
    "troglitazone", "tolazamide", "examide", "citoglipton", "insulin",
    "glyburide-metformin", "glipizide-metformin", "glimepiride-pioglitazone",
    "metformin-rosiglitazone", "metformin-pioglitazone", "change", "diabetesMed",
    "readmitted",
]


def sql_name(column: str) -> str:
    return column.lower().replace("-", "_")


RAW_COLUMNS = [sql_name(c) for c in SOURCE_COLUMNS]

INTEGER_COLUMNS = {
    "encounter_id": (1, None),
    "patient_nbr": (1, None),
    "time_in_hospital": (1, 14),
    "num_lab_procedures": (0, None),
    "num_procedures": (0, None),
    "num_medications": (0, None),
    "number_outpatient": (0, None),
    "number_emergency": (0, None),
    "number_inpatient": (0, None),
    "number_diagnoses": (1, None),
}

DIABETES_MEDS = [
    "metformin", "repaglinide", "nateglinide", "chlorpropamide", "glimepiride",
    "acetohexamide", "glipizide", "glyburide", "tolbutamide", "pioglitazone",
    "rosiglitazone", "acarbose", "miglitol", "troglitazone", "tolazamide",
    "examide", "citoglipton", "insulin", "glyburide_metformin", "glipizide_metformin",
    "glimepiride_pioglitazone", "metformin_rosiglitazone", "metformin_pioglitazone",
]
MED_VALUES = {"No", "Steady", "Up", "Down"}
KEPT_MEDS = ["metformin", "glipizide", "glyburide", "pioglitazone", "rosiglitazone", "glimepiride", "insulin"]

AGE_BINS = [
    "[0-10)", "[10-20)", "[20-30)", "[30-40)", "[40-50)",
    "[50-60)", "[60-70)", "[70-80)", "[80-90)", "[90-100)",
]
GENDERS = {"Female", "Male"}
GLU_VALUES = {"None", "Norm", ">200", ">300"}
A1C_VALUES = {"None", "Norm", ">7", ">8"}

TARGET_MAP = {"NO": 0, ">30": 1, "<30": 2}
CLASS_NAMES = {0: "no_readmission", 1: "late_readmission", 2: "early_readmission"}

ADMISSION_TYPE = {
    "1": "Emergency", "7": "Emergency", "2": "Urgent", "3": "Elective",
    "4": "Other", "5": "Unknown", "6": "Unknown", "8": "Unknown",
}
DISCHARGE_EXCLUDED = {"11", "13", "14", "19", "20", "21"}
DISCHARGE_DISPOSITION = {
    "1": "Home",
    "6": "Home health", "8": "Home health",
    **{k: "Transfer" for k in ("2", "3", "4", "5", "10", "15", "16", "17", "22", "23", "24", "27", "28", "29", "30")},
    **{k: "Unknown" for k in ("18", "25", "26")},
}
ADMISSION_SOURCE = {
    "7": "Emergency",
    **{k: "Referral" for k in ("1", "2", "3")},
    **{k: "Transfer" for k in ("4", "5", "6", "10", "18", "19", "22", "25", "26")},
    **{k: "Unknown" for k in ("9", "15", "17", "20", "21")},
}
TOP_SPECIALTIES = [
    "InternalMedicine", "Emergency/Trauma", "Family/GeneralPractice", "Cardiology",
    "Surgery-General", "Nephrology", "Orthopedics", "Orthopedics-Reconstructive", "Radiologist",
]

NUMERIC_FEATURES = [
    "time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
    "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses",
    "diabetes_meds_active", "diabetes_meds_changed",
]
ORDINAL_FEATURES = ["age"]
CATEGORICAL_FEATURES = [
    "race", "gender", "admission_type", "discharge_disposition", "admission_source",
    "medical_specialty", "diag_1_group", "diag_2_group", "diag_3_group",
    "max_glu_serum", "a1cresult", *KEPT_MEDS, "change", "diabetesmed",
]
FEATURES = NUMERIC_FEATURES + ORDINAL_FEATURES + CATEGORICAL_FEATURES
TARGET = "target"
