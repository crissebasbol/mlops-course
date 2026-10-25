import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from .config import (
    AGE_BINS,
    CATEGORICAL_FEATURES,
    CLASS_NAMES,
    FEATURES,
    MLFLOW_EXPERIMENT,
    NUMERIC_FEATURES,
    ORDINAL_FEATURES,
    RANDOM_STATE,
    SELECTION_METRIC,
    TARGET,
)

CLASSES = sorted(CLASS_NAMES)

# MLflow serializa con skops; estos son los tipos de arbol de cada modelo que skops pide
# declarar como confiables (los generamos nosotros mismos en este DAG).
SKOPS_TRUSTED_TYPES = {
    "logistic_regression": [],
    "random_forest": ["sklearn.tree._tree.Tree"],
    "hist_gradient_boosting": ["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"],
}


def candidates() -> dict:
    return {
        "logistic_regression": LogisticRegression(
            max_iter=2000, C=0.5, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=14, min_samples_leaf=5,
            class_weight="balanced_subsample", n_jobs=2, random_state=RANDOM_STATE,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
            class_weight="balanced", early_stopping=True, random_state=RANDOM_STATE,
        ),
    }


def build_pipeline(model_type: str) -> Pipeline:
    """Codificacion y escalado dentro del Pipeline: la API recibe las features
    de la tabla clean y aplica exactamente la misma transformacion."""
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("age", OrdinalEncoder(categories=[AGE_BINS], handle_unknown="use_encoded_value", unknown_value=-1), ORDINAL_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("preprocessor", preprocessor), ("model", candidates()[model_type])])


def split_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    return df[FEATURES], df[TARGET].astype("int64")


def evaluate(model, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    pred = model.predict(X)
    proba = model.predict_proba(X)
    metrics = {
        "f1_macro": f1_score(y, pred, average="macro"),
        "f1_weighted": f1_score(y, pred, average="weighted"),
        "precision_macro": precision_score(y, pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y, pred, average="macro", zero_division=0),
        "accuracy": accuracy_score(y, pred),
        "roc_auc_ovr": roc_auc_score(y, proba, multi_class="ovr", average="macro", labels=CLASSES),
    }
    per_class_f1 = f1_score(y, pred, average=None, labels=CLASSES, zero_division=0)
    per_class_recall = recall_score(y, pred, average=None, labels=CLASSES, zero_division=0)
    for cls, f1, rec in zip(CLASSES, per_class_f1, per_class_recall):
        metrics[f"f1_{CLASS_NAMES[cls]}"] = f1
        metrics[f"recall_{CLASS_NAMES[cls]}"] = rec
    return {k: float(v) for k, v in metrics.items()}


def _simple_params(estimator) -> dict:
    return {k: v for k, v in estimator.get_params().items() if isinstance(v, (int, float, str, bool, type(None)))}


def train_and_log(model_type: str, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, tags: dict) -> dict:
    """Entrena un candidato y registra el run en MLflow: params, metricas de
    train/val/test, matriz de confusion, reporte y el modelo serializado."""
    X_train, y_train = split_xy(train)
    X_val, y_val = split_xy(val)
    X_test, y_test = split_xy(test)

    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    run_name = f"{model_type}-batch{tags['batch_id']}"
    with mlflow.start_run(run_name=run_name) as run:
        pipeline = build_pipeline(model_type)
        pipeline.fit(X_train, y_train)

        mlflow.set_tags({**tags, "model_type": model_type})
        mlflow.log_params({
            "model_type": model_type,
            "selection_metric": SELECTION_METRIC,
            "n_train": len(train),
            "n_val": len(val),
            "n_test": len(test),
            **{f"model__{k}": v for k, v in _simple_params(pipeline.named_steps["model"]).items()},
        })

        metrics = {}
        for prefix, X, y in (("train", X_train, y_train), ("val", X_val, y_val), ("test", X_test, y_test)):
            metrics.update({f"{prefix}_{k}": v for k, v in evaluate(pipeline, X, y).items()})
        mlflow.log_metrics(metrics)

        labels = [CLASS_NAMES[c] for c in CLASSES]
        test_pred = pipeline.predict(X_test)
        matrix = confusion_matrix(y_test, test_pred, labels=CLASSES)
        mlflow.log_dict({"labels": labels, "matrix": matrix.tolist()}, "evaluation/confusion_matrix_test.json")
        mlflow.log_text(
            classification_report(y_test, test_pred, labels=CLASSES, target_names=labels, zero_division=0),
            "evaluation/classification_report_test.txt",
        )
        class_balance = train[TARGET].map(CLASS_NAMES).value_counts(normalize=True).round(4).to_dict()
        mlflow.log_dict({"train_class_balance": class_balance}, "data/class_balance.json")

        example = X_val.head(5)
        signature = infer_signature(example, pipeline.predict_proba(example))
        info = mlflow.sklearn.log_model(
            pipeline,
            name="model",
            signature=signature,
            input_example=example,
            skops_trusted_types=SKOPS_TRUSTED_TYPES[model_type] or None,
        )

    return {
        "model_type": model_type,
        "run_id": run.info.run_id,
        "model_uri": info.model_uri,
        "score": metrics[SELECTION_METRIC],
        "test_f1_macro": metrics["test_f1_macro"],
    }


def score(model, df: pd.DataFrame) -> float:
    """Metrica de seleccion (F1 macro) de un modelo ya entrenado sobre un split."""
    X, y = split_xy(df)
    return float(f1_score(y, model.predict(X), average="macro"))


def summary(df: pd.DataFrame) -> dict:
    counts = df.groupby("split")[TARGET].value_counts().unstack(fill_value=0)
    return {split: {CLASS_NAMES[c]: int(n) for c, n in row.items()} for split, row in counts.iterrows()}

