# Trainer

Contenedor de **una sola ejecución** que entrena dos Random Forest de Covertype,
los registra en MLflow como versiones de `covertype_rf` y le pone el alias
`champion` al mejor. Después termina
(`Exited (0)`), y solo entonces arranca la API.

## Qué hace

1. Si `covertype_rf@champion` ya existe, no hace nada (así un `docker compose up`
   repetido o un `--scale` no vuelven a entrenar).
2. Lee el CSV de Covertype. No se copia: se monta el mismo archivo de
   `taller4/jupyter/covertype.csv` como volumen de solo lectura.
3. Aplica la misma limpieza del notebook de taller4 (columnas en minúscula,
   `dropna`, `drop_duplicates`, split estratificado 80/20).
4. Entrena el mismo pipeline (`OneHotEncoder` + `RandomForestClassifier`) con
   cada configuración de `RF_CONFIGS`, como en el notebook de taller4: un run
   padre `grid_rf_taller5` con un run anidado por modelo (`rf_01`, `rf_02`). Cada
   run registra parámetros, métricas y su modelo como una versión nueva de
   `covertype_rf`.
5. Le pone el alias `champion` a la versión con mejor `f1_macro`. Esa es la que
   carga la API; las dos versiones se pueden ver en `GET /models`.

| Run     | `n_estimators` | `max_depth` | `max_features` |
|---------|---------------:|------------:|----------------|
| `rf_01` | 25             | 15          | `sqrt`         |
| `rf_02` | 50             | 12          | `sqrt`         |

Para reentrenar a mano:

```bash
FORCE_TRAIN=true docker compose up trainer
```

Las réplicas de la API cargan el modelo al arrancar; después de reentrenar hay
que reiniciarlas (`docker compose restart api`).
