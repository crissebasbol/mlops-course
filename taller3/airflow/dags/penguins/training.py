import re
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    adjusted_rand_score,
    classification_report,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .config import (
    CATEGORICAL_FEATURES,
    GMM_FEATURES,
    MODELS_DIR,
    N_CLUSTERS,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    TEST_SIZE,
)

VERSION_PATTERN = re.compile(r"^v(\d+)\.pkl$")


class ModelType(Enum):
    GMM = 1
    RF = 2

    @property
    def carpeta(self) -> str:
        return self.name.lower()


class ModelStore:
    """Guarda los modelos versionados"""

    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = Path(models_dir)

    def next_version_path(self, model_type: ModelType) -> Path:
        """Ruta del siguiente vN.pkl: busca el numero mas alto y suma uno."""
        subdir = self.models_dir / model_type.carpeta
        subdir.mkdir(parents=True, exist_ok=True)

        versiones = [
            int(m.group(1))
            for f in subdir.iterdir()
            if (m := VERSION_PATTERN.match(f.name))
        ]
        siguiente = (max(versiones) + 1) if versiones else 1
        return subdir / f"v{siguiente}.pkl"

    def save(self, payload: dict, model_type: ModelType) -> Path:
        ruta = self.next_version_path(model_type)
        joblib.dump(payload, ruta)
        print(f"Modelo guardado en: {ruta}")
        return ruta


class BaseTrainer(ABC):
    """Entrenar modelos de ML y guardar"""

    model_type: ModelType

    @abstractmethod
    def train(self, df: pd.DataFrame) -> tuple[dict, dict]:
        """Devuelve (payload a serializar, metricas para el log/XCom)."""

    def run(self, df: pd.DataFrame, store: ModelStore) -> dict:
        payload, metricas = self.train(df)
        ruta = store.save(payload, self.model_type)
        return {
            "model_type": self.model_type.carpeta,
            "version": ruta.stem,
            "path": str(ruta),
            **metricas,
        }


class RandomForestTrainer(BaseTrainer):
    """Supervisado: prueba tres clasificadores y se queda con el mejor."""

    model_type = ModelType.RF

    def train(self, df: pd.DataFrame) -> tuple[dict, dict]:
        df = df.dropna().reset_index(drop=True).copy()

        # Codificacion de categoricas de entrada + target.
        encoders = {}
        for col in CATEGORICAL_FEATURES:
            enc = LabelEncoder()
            df[col] = enc.fit_transform(df[col])
            encoders[col] = enc

        species_encoder = LabelEncoder()
        df["species"] = species_encoder.fit_transform(df["species"])
        encoders["species"] = species_encoder

        # Se entrena con arreglos de numpy (no DataFrame) porque la API hace
        # inferencia con numpy: asi el modelo no guarda nombres de columnas y
        # no aparecen advertencias de scikit-learn al predecir.
        feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        X = df[feature_columns].to_numpy()
        y = df["species"].to_numpy()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
        )

        models = {
            "logistic_regression": Pipeline(
                [("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))]
            ),
            "decision_tree": DecisionTreeClassifier(random_state=RANDOM_STATE),
            "random_forest": RandomForestClassifier(
                n_estimators=200, random_state=RANDOM_STATE
            ),
        }

        accuracies = {}
        species_names = list(encoders["species"].classes_)

        for name, model in models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            accuracies[name] = float(accuracy_score(y_test, y_pred))
            print(f"Modelo '{name}' -> accuracy: {accuracies[name]:.4f}")
            print(classification_report(
                y_test, y_pred,
                labels=range(len(species_names)),
                target_names=species_names,
            ))

        best_model = max(accuracies, key=accuracies.get)
        print(f"Mejor modelo: '{best_model}' ({accuracies[best_model]:.4f})")

        payload = {
            "models": models,
            "encoders": encoders,
            "metadata": {
                "feature_columns": feature_columns,
                "numeric_features": NUMERIC_FEATURES,
                "categorical_features": CATEGORICAL_FEATURES,
                "available_models": list(models.keys()),
                "default_model": best_model,
                "accuracies": accuracies,
            },
        }
        metricas = {
            "best_model": best_model,
            "accuracy": accuracies[best_model],
            "n_samples": int(len(df)),
        }
        return payload, metricas


class GaussianMixtureTrainer(BaseTrainer):
    """No supervisado: agrupa en 3 clusters y los mapea a especies."""

    model_type = ModelType.GMM

    def train(self, df: pd.DataFrame) -> tuple[dict, dict]:
        df = df.dropna(subset=GMM_FEATURES).copy()
        # Igual que en rf: numpy para que la inferencia desde la API coincida.
        X = df[GMM_FEATURES].to_numpy()

        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("gmm", GaussianMixture(
                n_components=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10
            )),
        ])

        labels = pipeline.fit_predict(X)
        silhouette = float(silhouette_score(X, labels))
        print(f"Muestras usadas: {len(X)}")
        print(f"Silhouette score: {silhouette:.3f}")

        ari = float(adjusted_rand_score(df["species"], labels))
        print(f"Adjusted Rand Index vs especie real: {ari:.3f}")

        # Cada cluster se etiqueta con la especie mayoritaria que cayo en el.
        cluster_to_species = (
            df.assign(cluster=labels)
            .groupby("cluster")["species"]
            .agg(lambda s: s.mode()[0])
            .to_dict()
        )
        cluster_to_species = {int(k): str(v) for k, v in cluster_to_species.items()}
        print(f"Mapeo cluster -> especie: {cluster_to_species}")

        predicted_species = [cluster_to_species[c] for c in labels]
        accuracy = float(accuracy_score(df["species"], predicted_species))
        print(f"Accuracy (especie mayoritaria por cluster): {accuracy:.3f}")

        payload = {
            "pipeline": pipeline,
            "cluster_to_species": cluster_to_species,
            "features": GMM_FEATURES,
        }
        metricas = {
            "silhouette": silhouette,
            "adjusted_rand_index": ari,
            "accuracy": accuracy,
            "n_samples": int(len(df)),
        }
        return payload, metricas
