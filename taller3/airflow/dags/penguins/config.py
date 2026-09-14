import os
from pathlib import Path

# Conexion de Airflow hacia postgres-data. La define la variable de entorno
# AIRFLOW_CONN_MLOPS_DATA en el docker-compose, no hay que crearla a mano.
DATA_CONN_ID = "mlops_data"

CSV_PATH = Path(os.environ.get("PENGUINS_CSV_PATH", "/opt/airflow/data/penguins.csv"))
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/opt/airflow/models"))

# Tablas de la base de datos
RAW_TABLE = "raw_penguins"
CLEAN_TABLE = "clean_penguins"

# Columnas del CSV
CSV_COLUMNS = [
    "rowid",
    "species",
    "island",
    "bill_length_mm",
    "bill_depth_mm",
    "flipper_length_mm",
    "body_mass_g",
    "sex",
    "year",
]

# Features supervisado (RF)
NUMERIC_FEATURES = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
CATEGORICAL_FEATURES = ["island", "sex"]

# Features no supervisado (GMM)
GMM_FEATURES = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
N_CLUSTERS = 3  # Adelie, Chinstrap, Gentoo

# Parametros de entrenamiento
TEST_SIZE = 0.2
RANDOM_STATE = 42
