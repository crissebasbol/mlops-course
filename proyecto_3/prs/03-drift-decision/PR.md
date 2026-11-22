# PR 3: drift y decisión de entrenamiento (Cristian)

Depende del PR 1 (ya fusionado). Puede abrirse en paralelo con el PR 2.

## Pasos

```bash
git clone git@github.com:crissebasbol/housing-price-mlops.git   # si aún no lo tienes
cd housing-price-mlops
git switch master && git pull
git switch -c feature/drift-decision

# copiar la carpeta housing_ml/ de este directorio sobre la raíz del repo

uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest

git add housing_ml/src/housing_ml/drift.py housing_ml/tests/test_drift.py
git commit -m "Detección de drift y categorías nuevas"
git add housing_ml/src/housing_ml/decision.py housing_ml/tests/test_decision.py
git commit -m "Regla de decisión de entrenamiento"
git push -u origin feature/drift-decision
```

Abrir el PR en GitHub (la plantilla aparece sola) con:

**Título:** `Drift y decisión de entrenamiento`

**Qué cambia**

- `drift.py`: PSI por cuantiles y Kolmogorov-Smirnov para variables numéricas, PSI para categóricas y detección de categorías nuevas con su porcentaje de filas.
- `decision.py`: la regla que decide si un lote justifica entrenar, con el motivo en español:
  1. No entrena si el esquema es inválido, el lote llega vacío, más del 20 % de las filas no pasan calidad, o hay menos de 10.000 filas válidas o menos del 5 % del acumulado.
  2. Entrena si no hay modelo productivo (línea base).
  3. Entrena si se cumple alguna señal: PSI > 0,2 en una variable numérica; `status` o `state` nuevos en al menos 2 % del lote; el acumulado creció 20 % desde el último entrenamiento; el MAPE del modelo productivo en el lote nuevo es 1,1 veces su referencia; o cambió la distribución de las consultas reales (con al menos 500 eventos).
  4. Si no, no entrena por falta de cambios relevantes.

**Por qué**

RF3 (validar distribución y categorías nuevas) y RF4: la decisión no depende solo del conteo de registros ni de la periodicidad, sino de varias señales técnicas, y cada decisión deja su razón para la auditoría y Streamlit.

**Cómo se probó**

`ruff` y `pytest` (19 pruebas nuevas: PSI y KS con y sin cambio de distribución, referencia constante, categorías nuevas, y cada camino de la decisión con escenarios como los de los lotes reales).

## Para explicarlo

- **PSI** (Population Stability Index) compara qué proporción de datos cae en cada tramo de la distribución de referencia. Por debajo de 0,1 no hay cambio; por encima de 0,2 el cambio es significativo (umbral estándar).
- **KS** se reporta como complemento: con cientos de miles de filas su p-valor casi siempre es diminuto, por eso la decisión usa el PSI.
- **Categorías nuevas:** solo `status` y `state` son señal de entrenamiento. Ciudades, códigos postales y corredores cambian en todos los lotes (alta cardinalidad) y el encoder ya los maneja como desconocidos.
- **Lote 3 real (Massachusetts, 4.055 filas):** trae un estado nuevo, pero es el 1 % del acumulado; no entrena y sus filas quedan en CLEAN para el siguiente entrenamiento.
