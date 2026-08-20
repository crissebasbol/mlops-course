import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CSV_PATH = "penguins.csv"
MODEL_PATH = "penguin_kmeans.pkl"
FEATURES = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
N_CLUSTERS = 3  # Adelie, Chinstrap, Gentoo

df = pd.read_csv(CSV_PATH)
df = df.dropna(subset=FEATURES)
X = df[FEATURES]

pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="mean")),
    ("scaler", StandardScaler()),
    ("kmeans", KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)),
])

labels = pipeline.fit_predict(X)

print(f"Muestras usadas: {len(X)}")
print(f"Silhouette score: {silhouette_score(X, labels):.3f}")
if "species" in df.columns:
    ari = adjusted_rand_score(df["species"], labels)
    print(f"Adjusted Rand Index vs especie real: {ari:.3f}")

joblib.dump(pipeline, MODEL_PATH)
print(f"Modelo guardado en {MODEL_PATH}")
