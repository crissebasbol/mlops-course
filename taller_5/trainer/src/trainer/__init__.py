import os
import time
import warnings

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from sklearn.compose import make_column_transformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CSV_PATH = os.environ.get("CSV_PATH", "/data/covertype.csv")
EXPERIMENT_NAME = os.environ.get("EXPERIMENT_NAME", "covertype_rf")
MODEL_NAME = os.environ.get("MODEL_NAME", "covertype_rf")
MODEL_ALIAS = os.environ.get("MODEL_ALIAS", "champion")
FORCE_TRAIN = os.environ.get("FORCE_TRAIN", "false").lower() == "true"

RF_CONFIGS = [
    {"n_estimators": 25, "max_depth": 15, "max_features": "sqrt"},
    {"n_estimators": 50, "max_depth": 12, "max_features": "sqrt"},
]
TEST_SIZE = 0.2
RANDOM_STATE = 42

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
TARGET = "cover_type"

warnings.filterwarnings("ignore", message=".*sklearn.utils.parallel.delayed", category=UserWarning)


def champion_exists(client: MlflowClient) -> bool:
    try:
        client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
        return True
    except MlflowException:
        return False


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.lower() for c in df.columns]
    df = df[FEATURES + [TARGET]].dropna().drop_duplicates().reset_index(drop=True)
    for col in NUMERIC_FEATURES:
        df[col] = df[col].astype("float64")
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype(str).str.strip().astype("object")
    df[TARGET] = df[TARGET].astype("int64")
    return train_test_split(df, test_size=TEST_SIZE, stratify=df[TARGET], random_state=RANDOM_STATE)


def build_pipeline(**rf_params) -> Pipeline:
    column_trans = make_column_transformer(
        (OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        remainder="passthrough",
    )
    return Pipeline(steps=[
        ("column_trans", column_trans),
        ("RandomForestClassifier", RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1, **rf_params)),
    ])


def train_and_log(params: dict, run_name: str, X_train, y_train, X_test, y_test) -> dict:
    with mlflow.start_run(run_name=run_name, nested=True):
        pipe = build_pipeline(**params)
        inicio = time.perf_counter()
        pipe.fit(X_train, y_train)
        fit_time = time.perf_counter() - inicio

        y_pred = pipe.predict(X_test)
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "f1_macro": f1_score(y_test, y_pred, average="macro"),
            "f1_weighted": f1_score(y_test, y_pred, average="weighted"),
            "fit_time_s": fit_time,
        }

        # Cada replica de la API tiene 1 CPU: se sirve con un solo hilo por prediccion.
        pipe.set_params(RandomForestClassifier__n_jobs=1)

        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        model_info = mlflow.sklearn.log_model(
            sk_model=pipe,
            name="model",
            signature=infer_signature(X_test, y_pred),
            input_example=X_test.head(3),
            registered_model_name=MODEL_NAME,
            skops_trusted_types=["sklearn.tree._tree.Tree"],
        )

    version = str(model_info.registered_model_version)
    print(f"{run_name} {params} -> v{version} accuracy={metrics['accuracy']:.4f} f1_macro={metrics['f1_macro']:.4f}")
    return {"run": run_name, "version": version, "params": params, **metrics}


def main() -> None:
    client = MlflowClient()
    print(f"tracking uri: {mlflow.get_tracking_uri()}")

    if champion_exists(client) and not FORCE_TRAIN:
        mv = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
        print(f"{MODEL_NAME}@{MODEL_ALIAS} ya existe (v{mv.version}), no se entrena de nuevo")
        return

    train_df, test_df = load_data()
    X_train, y_train = train_df[FEATURES], train_df[TARGET]
    X_test, y_test = test_df[FEATURES], test_df[TARGET]
    print(f"train: {X_train.shape}, test: {X_test.shape}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="grid_rf_taller5"):
        mlflow.log_params({"n_combinations": len(RF_CONFIGS), "random_state": RANDOM_STATE})
        results = [
            train_and_log(params, f"rf_{i:02d}", X_train, y_train, X_test, y_test)
            for i, params in enumerate(RF_CONFIGS, start=1)
        ]

    for r in results:
        client.update_model_version(
            MODEL_NAME,
            r["version"],
            description=f"Taller 5 {r['run']} {r['params']}: accuracy={r['accuracy']:.4f}, f1_macro={r['f1_macro']:.4f}",
        )

    best = max(results, key=lambda r: r["f1_macro"])
    client.set_registered_model_alias(MODEL_NAME, MODEL_ALIAS, best["version"])
    client.update_registered_model(
        MODEL_NAME,
        description="Random Forest para Covertype (taller 5). El alias 'champion' apunta al mejor f1_macro.",
    )
    print(f"{MODEL_NAME}@{MODEL_ALIAS} -> v{best['version']} ({best['run']}, f1_macro={best['f1_macro']:.4f})")
