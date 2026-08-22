"""
train.py

Este script hace las dos etapas clasicas de un pipeline de ML "nivel 0":
    1. Procesamiento de datos (limpieza + codificacion)
    2. Entrenamiento del modelo (en realidad, entreno varios para el bono)

IMPORTANTE (requisito del taller): NO se usa la libreria `palmerpenguins`.
Los datos se leen directamente del archivo penguins.csv que ya viene en
la carpeta. Esto simula el caso real de MLOps donde uno no vuelve a bajar
los datos de una fuente externa cada vez que entrena, sino que consume un
archivo/dataset versionado.
"""

import json

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

# Carpeta donde voy a dejar todo lo que la API necesita despues:
# los modelos entrenados y los encoders (sin los encoders no puedo
# volver a convertir texto <-> numero de la misma forma en inferencia).
MODELS_DIR = "models"

# Estas son las columnas numericas que le voy a pasar al modelo.
# "year" la dejo por fuera porque es metadata del muestreo (el anio en que
# se tomo la medicion), no una caracteristica biologica del pinguino, asi
# que no deberia ayudar a predecir la especie.
NUMERIC_FEATURES = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]

# Estas son las columnas categoricas de entrada (no confundir con la
# columna "species", que es el target y se codifica aparte).
CATEGORICAL_FEATURES = ["island", "sex"]


def load_data(path: str = "penguins.csv") -> pd.DataFrame:
    """Lee el csv y bota la columna rowid, que es solo un indice y no aporta info."""
    df = pd.read_csv(path)
    df = df.drop(columns=["rowid"])
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Manejo de valores faltantes (NA).

    Explorando el csv vi que hay pocas filas con NA (algunas donde
    practicamente toda la fila viene vacia, incluido el sexo). Como son
    pocas comparado con el total del dataset (~344 filas), en vez de
    inventar valores con una imputacion (media/mediana) decidi eliminar
    esas filas. Para un ejercicio de clase esto es mas simple y evita
    meterle sesgo al modelo con datos "inventados".
    """
    return df.dropna().reset_index(drop=True)


def encode_features(df: pd.DataFrame):
    """
    Codifica las variables categoricas de entrada (island, sex) y el target
    (species) a numeros, porque los modelos de sklearn no entienden texto.

    Uso LabelEncoder porque island y sex tienen pocas categorias y no hay
    una relacion de orden entre ellas, pero para simplificar el pipeline
    (y porque los modelos que uso, como el arbol y el random forest,
    manejan bien variables categoricas codificadas asi) no hice One-Hot.
    Ojo: para LogisticRegression esto no es lo mas "correcto" en teoria
    (asume una escala numerica que no existe), pero para efectos del
    taller funciona bien y mantiene el pipeline simple.

    Devuelve el dataframe ya codificado y los encoders, porque en la API
    voy a necesitar los MISMOS encoders para transformar lo que mande el
    usuario (si entreno con un encoder y en la API uso otro, los numeros
    no significarian lo mismo y el modelo prediria cualquier cosa).
    """
    df = df.copy()
    encoders = {}

    for col in CATEGORICAL_FEATURES:
        encoder = LabelEncoder()
        df[col] = encoder.fit_transform(df[col])
        encoders[col] = encoder

    species_encoder = LabelEncoder()
    df["species"] = species_encoder.fit_transform(df["species"])
    encoders["species"] = species_encoder

    return df, encoders


def build_models() -> dict:
    """
    Bono del taller: en vez de entrenar un solo modelo, entreno varios
    "candidatos" razonables para un problema de clasificacion multiclase
    chiquito como este. Asi la API puede exponer un endpoint para elegir
    con cual de todos hacer la inferencia, en vez de quedar amarrada a
    un unico modelo.
    """
    return {
        # body_mass_g esta en miles y bill_depth_mm en decenas: sin
        # escalar, LogisticRegression no convergia (probado en la
        # practica). Por eso va envuelta en un Pipeline con
        # StandardScaler. El arbol y el random forest no lo necesitan
        # porque no son sensibles a la escala de las features.
        "logistic_regression": Pipeline(
            [("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))]
        ),
        "decision_tree": DecisionTreeClassifier(random_state=42),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=42),
    }


def main():
    df = load_data()
    df = clean_data(df)
    df, encoders = encode_features(df)

    feature_columns = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    X = df[feature_columns]
    y = df["species"]

    # stratify=y para que train y test conserven la misma proporcion de
    # especies (Adelie/Chinstrap/Gentoo), ya que el dataset no esta
    # balanceado entre especies.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    models = build_models()
    accuracies = {}
    species_names = encoders["species"].classes_

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        accuracies[name] = acc
        print(f"[train.py] Modelo '{name}' -> accuracy en test: {acc:.4f}")
        print(f"[train.py] Classification report para '{name}' (por especie):")
        print(
            classification_report(
                y_test, y_pred, labels=range(len(species_names)), target_names=species_names
            )
        )

    best_model = max(accuracies, key=accuracies.get)
    print(f"[train.py] Mejor modelo segun accuracy: '{best_model}' ({accuracies[best_model]:.4f})")

    # Guardo todo lo necesario para que la API pueda hacer inferencia
    # sin tener que volver a leer el csv ni reentrenar nada.
    import os

    os.makedirs(MODELS_DIR, exist_ok=True)

    for name, model in models.items():
        joblib.dump(model, f"{MODELS_DIR}/{name}.pkl")

    for name, encoder in encoders.items():
        joblib.dump(encoder, f"{MODELS_DIR}/{name}_encoder.pkl")

    # metadata.json le dice a la API que modelos existen, que orden de
    # features espera cada uno y como se llama el "mejor" por defecto.
    metadata = {
        "feature_columns": feature_columns,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "available_models": list(models.keys()),
        "default_model": best_model,
        "accuracies": accuracies,
    }
    with open(f"{MODELS_DIR}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[train.py] Modelos, encoders y metadata guardados en '{MODELS_DIR}/'")


if __name__ == "__main__":
    main()
