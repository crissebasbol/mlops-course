import os

from airflow.datasets import Dataset


def _env_bool(nombre: str, defecto: str) -> bool:
    return os.environ.get(nombre, defecto).strip().lower() in {"1", "true", "yes", "si"}


# Conexion de Airflow hacia la base de datos `covertype` de postgres-data.
DATA_CONN_ID = "covertype_data"

DATA_SOURCE_MODE = os.environ.get("DATA_SOURCE_MODE", "auto").strip().lower()
REMOTE_API_URL = os.environ.get("REMOTE_API_URL", "http://10.43.97.110:8080").rstrip("/")
LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "http://source-app:80").rstrip("/")
GROUP_NUMBER = int(os.environ.get("GROUP_NUMBER", "1"))
STATUS_TIMEOUT_SECONDS = float(os.environ.get("STATUS_TIMEOUT_SECONDS", "5"))
DATA_TIMEOUT_SECONDS = float(os.environ.get("DATA_TIMEOUT_SECONDS", "120"))

COLLECT_INTERVAL_SECONDS = int(os.environ.get("COLLECT_INTERVAL_SECONDS", "300"))
REQUIRED_BATCHES = int(os.environ.get("REQUIRED_BATCHES", "10"))
AUTO_RESTART_COLLECTION = _env_bool("AUTO_RESTART_COLLECTION", "true")

RAW_TABLE = "raw_covertype"
CLEAN_TABLE = "clean_covertype"
TRAIN_TABLE = "train_covertype"
LOG_TABLE = "collection_log"

# Dataset de Airflow que conecta los dos DAGs: la recoleccion lo actualiza
# cuando completa los 10 batches y eso dispara el DAG de entrenamiento.
TRAINING_DATASET = Dataset("postgres://postgres-data:5432/covertype/public/train_covertype")

# Orden en que la API entrega cada fila.
RAW_COLUMNS = [
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
    "wilderness_area",
    "soil_type",
    "cover_type",
]
NUMERIC_FEATURES = RAW_COLUMNS[:10]
CATEGORICAL_FEATURES = ["wilderness_area", "soil_type"]
TARGET = "cover_type"

WILDERNESS_AREAS = ["Rawah", "Neota", "Commanche", "Cache"]
N_COVER_TYPES = 7

TRAIN_FRACTION = 80  # porcentaje de filas que van a train (el resto a test)
RANDOM_STATE = 42
TRAIN_ONLY_IF_NO_MODEL = _env_bool("TRAIN_ONLY_IF_NO_MODEL", "true")

RF_PARAMS = {"n_estimators": 100, "max_depth": 25, "min_samples_leaf": 2, "n_jobs": 2}
GMM_PARAMS = {"n_components": N_COVER_TYPES, "covariance_type": "full", "n_init": 3, "max_iter": 200}
SILHOUETTE_SAMPLE = 5000

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "admin123")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "models")
MINIO_SECURE = _env_bool("MINIO_SECURE", "false")
