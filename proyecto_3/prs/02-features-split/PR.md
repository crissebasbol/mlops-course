# PR 2: features, huellas y split (Fabián Ramírez)

Depende del PR 1 (ya fusionado). Puede abrirse en paralelo con el PR 3.

## Pasos

```bash
git clone git@github.com:crissebasbol/housing-price-mlops.git   # si aún no lo tienes
cd housing-price-mlops
git switch master && git pull
git switch -c feature/features-split

# copiar la carpeta housing_ml/ de este directorio sobre la raíz del repo
# (agrega housing_ml/src/housing_ml/features.py y housing_ml/tests/test_features.py)

uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest

git add housing_ml/src/housing_ml/features.py housing_ml/tests/test_features.py
git commit -m "Features, huellas SHA-256 y split estable"
git push -u origin feature/features-split
```

Abrir el PR en GitHub (la plantilla aparece sola) con:

**Título:** `Features, huellas de datos y split estable`

**Qué cambia**

`features.py` del paquete `housing_ml`:

- `row_hash` y `payload_hash`: huella SHA-256 de cada fila y de cada lote sobre JSON canónico (claves ordenadas).
- `split_for` / `assign_splits`: split estable por hash de la fila: 70 % train, 10 % val, 10 % test y 10 % holdout.
- `FeatureBuilder`: transformador de scikit-learn que recibe los campos crudos de la API y deriva `prev_sold_year`, `city_state` y `zip3`; las categorías vacías quedan como `unknown`.

**Por qué**

- La huella del lote detecta lotes repetidos después de reiniciar la API de datos, así no se reprocesan (RF1).
- El split por hash no cambia entre ejecuciones: el holdout siempre contiene las mismas filas y nunca se usa para entrenar, así el modelo productivo y el candidato se comparan sobre los mismos datos (RF6).
- Las features se derivan dentro del pipeline del modelo: el entrenamiento y la API transforman exactamente igual (sin training-serving skew).

**Cómo se probó**

`ruff` y `pytest` (5 pruebas nuevas: hash independiente del orden de claves, detección de lotes repetidos, split estable y balanceado, features derivadas y valores faltantes o desconocidos).

## Para explicarlo

- **¿Por qué un hash y no un id?** La API no entrega ids de fila. El hash del contenido identifica la fila y es igual cada vez que llega, así sirve también como llave entre RAW y CLEAN.
- **¿Por qué el split por hash?** Con `train_test_split` aleatorio, cada entrenamiento particiona distinto y las métricas entre versiones no son comparables. Con el hash, una fila siempre cae en el mismo grupo.
- **¿Por qué `FeatureBuilder` dentro del modelo?** La API manda los campos tal como los escribe el usuario; si la transformación viviera fuera del modelo, habría que duplicarla en la API y podría divergir.
