from abc import ABC, abstractmethod
from enum import Enum

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    adjusted_rand_score,
    classification_report,
    f1_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (
    CATEGORICAL_FEATURES,
    GMM_PARAMS,
    N_COVER_TYPES,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    RF_PARAMS,
    SILHOUETTE_SAMPLE,
    TARGET,
)
from .storage import ModelRegistry


class ModelType(str, Enum):
    RF = "rf"
    GMM = "gmm"


class BaseTrainer(ABC):
    """Entrena un tipo de modelo y lo guarda como version nueva en MinIO."""

    model_type: ModelType

    @abstractmethod
    def train(self, train_df: pd.DataFrame, test_df: pd.DataFrame) -> tuple[dict, dict]:
        """Devuelve (payload a serializar, metricas)."""

    def run(self, df: pd.DataFrame, registry: ModelRegistry, dag_run_id: str | None = None) -> dict:
        train_df = df[df["split"] == "train"].reset_index(drop=True)
        test_df = df[df["split"] == "test"].reset_index(drop=True)
        if train_df.empty or test_df.empty:
            raise ValueError(f"Datos insuficientes: train={len(train_df)}, test={len(test_df)}")
        print(f"[{self.model_type.value}] train={len(train_df)} filas, test={len(test_df)} filas")

        payload, metricas = self.train(train_df, test_df)
        payload["model_type"] = self.model_type.value

        metadata = registry.save(
            self.model_type.value,
            payload,
            {
                "dag_run_id": dag_run_id,
                "n_train": int(len(train_df)),
                "n_test": int(len(test_df)),
                "metrics": metricas,
                "features": {"numeric": NUMERIC_FEATURES, "categorical": payload["categorical_features"]},
            },
        )
        return {"version": metadata["version"], **metricas}


class RandomForestTrainer(BaseTrainer):
    """Supervisado: numericas tal cual + one-hot de Wilderness_Area y Soil_Type."""

    model_type = ModelType.RF

    def train(self, train_df, test_df):
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        pipeline = Pipeline([
            ("preprocess", ColumnTransformer([
                ("num", "passthrough", NUMERIC_FEATURES),
                # handle_unknown="ignore": un Soil_Type que no aparecio en
                # entrenamiento (p.ej. C5151) no rompe la prediccion.
                ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ])),
            ("clf", RandomForestClassifier(random_state=RANDOM_STATE, **RF_PARAMS)),
        ])
        pipeline.fit(train_df[features], train_df[TARGET].astype(int))

        y_test = test_df[TARGET].astype(int)
        y_pred = pipeline.predict(test_df[features])
        print(classification_report(y_test, y_pred, zero_division=0))

        metricas = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
            "params": RF_PARAMS,
        }
        payload = {
            "pipeline": pipeline,
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
        }
        return payload, metricas


class GaussianMixtureTrainer(BaseTrainer):
    """No supervisado: agrupa en 7 clusters (uno por tipo de cobertura) con las
    variables numericas y etiqueta cada cluster con el Cover_Type mayoritario."""

    model_type = ModelType.GMM

    def train(self, train_df, test_df):
        X_train = train_df[NUMERIC_FEATURES]
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("gmm", GaussianMixture(random_state=RANDOM_STATE, **GMM_PARAMS)),
        ])
        clusters = pipeline.fit_predict(X_train)

        # Cada cluster se etiqueta con la clase mayoritaria que cayo en el; si un
        # cluster quedo vacio se usa la clase mas frecuente del conjunto.
        clase_frecuente = int(train_df[TARGET].mode()[0])
        mayoritaria = (
            train_df.assign(cluster=clusters).groupby("cluster")[TARGET].agg(lambda s: int(s.mode()[0]))
        )
        cluster_to_cover_type = {
            int(c): int(mayoritaria.get(c, clase_frecuente)) for c in range(GMM_PARAMS["n_components"])
        }
        print(f"Mapeo cluster -> cover_type: {cluster_to_cover_type}")

        muestra = min(SILHOUETTE_SAMPLE, len(X_train))
        X_escalado = pipeline.named_steps["scaler"].transform(X_train)
        silhouette = float(silhouette_score(X_escalado, clusters, sample_size=muestra, random_state=RANDOM_STATE))
        ari = float(adjusted_rand_score(train_df[TARGET], clusters))

        y_test = test_df[TARGET].astype(int)
        y_pred = [cluster_to_cover_type[int(c)] for c in pipeline.predict(test_df[NUMERIC_FEATURES])]
        print(classification_report(y_test, y_pred, labels=range(N_COVER_TYPES), zero_division=0))

        metricas = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "silhouette": silhouette,
            "adjusted_rand_index": ari,
            "params": GMM_PARAMS,
        }
        payload = {
            "pipeline": pipeline,
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": [],
            "cluster_to_cover_type": cluster_to_cover_type,
        }
        return payload, metricas


TRAINERS: dict[str, type[BaseTrainer]] = {
    ModelType.RF.value: RandomForestTrainer,
    ModelType.GMM.value: GaussianMixtureTrainer,
}
