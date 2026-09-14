from .config import CLEAN_TABLE, CSV_PATH, RAW_TABLE
from .database import PenguinsDatabase
from .preprocessing import PenguinsPreprocessor


def borrar_datos() -> dict:
    db = PenguinsDatabase()
    db.reset_tables()

    restantes = {RAW_TABLE: db.count(RAW_TABLE), CLEAN_TABLE: db.count(CLEAN_TABLE)}
    print(f"Base de datos limpia. Filas restantes: {restantes}")
    return restantes


def cargar_datos_crudos() -> dict:
    """TAREA 2: carga el CSV a la tabla cruda, sin preprocesamiento."""
    db = PenguinsDatabase()
    filas = db.load_csv(CSV_PATH)

    print(f"Cargadas {filas} filas crudas en '{RAW_TABLE}' desde {CSV_PATH}")
    return {"filas_cargadas": filas}


def preprocesar_datos() -> dict:
    """TAREA 3: lee la tabla cruda, la limpia y escribe la tabla limpia."""
    db = PenguinsDatabase()
    df_crudo = db.read_raw()

    df_limpio = PenguinsPreprocessor().transform(df_crudo)
    db.write_clean(df_limpio)

    resumen = {
        "filas_crudas": len(df_crudo),
        "filas_limpias": len(df_limpio),
        "filas_descartadas": len(df_crudo) - len(df_limpio),
    }
    print(f"Preprocesamiento terminado: {resumen}")
    return resumen


def entrenar_modelos() -> dict:
    """TAREA 4: entrena rf y gmm con los datos limpios y los guarda versionados"""
    from .training import GaussianMixtureTrainer, ModelStore, RandomForestTrainer

    db = PenguinsDatabase()
    df = db.read_clean()
    print(f"Entrenando con {len(df)} filas de '{CLEAN_TABLE}'")

    store = ModelStore()
    resultados = {
        "rf": RandomForestTrainer().run(df, store),
        "gmm": GaussianMixtureTrainer().run(df, store),
    }

    for nombre, info in resultados.items():
        print(f"{nombre}: {info}")
    return resultados
