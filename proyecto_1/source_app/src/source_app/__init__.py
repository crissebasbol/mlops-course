"""
Replica local de la Data API
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import psycopg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

MIN_UPDATE_TIME = int(os.environ.get("MIN_UPDATE_TIME", "300"))  # Tiempo minimo para cambiar bloque de informacion
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://source_app:source_app123@postgres-data:5432/source_app"
)
CSV_PATH = Path(os.environ.get("CSV_PATH", "/app/data/covertype.csv"))

CSV_COLUMNS = [
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
    "wilderness_area",
    "soil_type",
    "cover_type",
]
GROUPS = range(1, 12)

logger = logging.getLogger("uvicorn.error")

# Se calcula al arrancar, igual que en el original: len(data) // 10
batch_size = 0


# ---------------------------
# Base de datos
# ---------------------------

def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def wait_for_database(intentos: int = 30, espera: float = 2.0) -> None:
    for intento in range(1, intentos + 1):
        try:
            with connect():
                return
        except psycopg.OperationalError:
            logger.info("Esperando a la base de datos (%s/%s)", intento, intentos)
            time.sleep(espera)
    raise RuntimeError("No fue posible conectarse a la base de datos")


def init_database() -> int:
    """Crea las tablas, carga el CSV si la tabla esta vacia y devuelve el total de filas."""
    columnas_sql = ",\n".join(f"{col} TEXT" for col in CSV_COLUMNS)
    with connect() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS covertype (
                id BIGSERIAL PRIMARY KEY,
                {columnas_sql}
            );
            CREATE TABLE IF NOT EXISTS group_state (
                group_number INTEGER PRIMARY KEY,
                last_update  DOUBLE PRECISION NOT NULL,
                batch        INTEGER NOT NULL
            );
        """)
        # Inicia en -1 para no agregar logica adicional de conteo, igual que el original.
        for grupo in GROUPS:
            conn.execute(
                "INSERT INTO group_state (group_number, last_update, batch) "
                "VALUES (%s, 0, -1) ON CONFLICT DO NOTHING",
                (grupo,),
            )

        total = conn.execute("SELECT count(*) FROM covertype").fetchone()[0]
        if total == 0:
            logger.info("Cargando %s en la tabla covertype", CSV_PATH)
            # El id se asigna en el orden del archivo, asi los rangos por batch
            # coinciden con las posiciones de la lista del original.
            copy_sql = (
                f"COPY covertype ({', '.join(CSV_COLUMNS)}) "
                "FROM STDIN WITH (FORMAT csv, HEADER true)"
            )
            with conn.cursor() as cur, cur.copy(copy_sql) as copy, CSV_PATH.open("rb") as fh:
                while chunk := fh.read(1024 * 1024):
                    copy.write(chunk)
            total = conn.execute("SELECT count(*) FROM covertype").fetchone()[0]
            logger.info("Cargadas %s filas", total)
    return total


# Definir la funcion para generar la fraccion de datos aleatoria
def get_batch_data(conn: psycopg.Connection, batch_number: int, batch_size: int) -> list[list[str]]:
    start_index = batch_number * batch_size
    end_index = start_index + batch_size
    muestra = batch_size // 10
    # Obtener datos aleatorios dentro del rango del grupo (id es 1-indexado).
    filas = conn.execute(
        f"SELECT {', '.join(CSV_COLUMNS)} FROM covertype "
        "WHERE id > %s AND id <= %s ORDER BY random() LIMIT %s",
        (start_index, end_index, muestra),
    ).fetchall()
    if len(filas) < muestra:
        # random.sample del original falla cuando el rango no alcanza.
        raise HTTPException(status_code=500, detail="Sample larger than population")
    return [list(fila) for fila in filas]


# ---------------------------
# Metadatos y documentacion
# ---------------------------

APP_DESCRIPTION = (
    """
    Replica local de la API para suministrar datos del Proyecto 2 (Extraccion de datos y entrenamiento de modelos).

    - Los datos se leen de Postgres (cargados una vez desde covertype.csv).
    - Los datos cambian cada MIN_UPDATE_TIME segundos (por defecto 300).
    - El dataset completo se divide en 10 lotes (batches). Cada request al endpoint /data
      devuelve una porcion aleatoria del batch vigente para el grupo solicitado.
    - Para obtener una muestra minima util, recolecta al menos una porcion de cada uno de los 10 batches.

    Orden de las columnas:
    # Elevation,
    # Aspect,
    # Slope,
    # Horizontal_Distance_To_Hydrology,
    # Vertical_Distance_To_Hydrology,
    # Horizontal_Distance_To_Roadways,
    # Hillshade_9am,
    # Hillshade_Noon,
    # Hillshade_3pm,
    # Horizontal_Distance_To_Fire_Points,
    # Wilderness_Area,
    # Soil_Type,
    # Cover_Type
    """
)

tags_metadata = [
    {"name": "info", "description": "Informacion general del servicio."},
    {"name": "data", "description": "Obtencion de porciones de datos por grupo y batch."},
    {"name": "admin", "description": "Operaciones de control para reiniciar conteos por grupo."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    global batch_size
    wait_for_database()
    batch_size = init_database() // 10
    logger.info("batch_size=%s, MIN_UPDATE_TIME=%ss", batch_size, MIN_UPDATE_TIME)
    yield


app = FastAPI(
    title="Proyecto 2 - Data API (source_app)",
    version="1.0.0",
    description=APP_DESCRIPTION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)


class BatchResponse(BaseModel):
    """Estructura de respuesta del endpoint /data."""

    group_number: int = Field(..., ge=1, le=11, description="Numero de grupo solicitado (1-10)")
    batch_number: int = Field(..., description="Indice del batch servido para el grupo")
    data: List[List[str]] = Field(
        ..., description="Filas del dataset (valores en formato string) para la porcion solicitada"
    )


@app.get(
    "/",
    tags=["info"],
    summary="Estado del servicio",
    description="Endpoint base para verificar disponibilidad. Devuelve informacion corta del proyecto.",
)
def root():
    return {"Proyecto 2": "Extracción de datos, entrenamiento de modelos."}


@app.get(
    "/data",
    tags=["data"],
    summary="Obtener porcion aleatoria del batch vigente",
    description=(
        "Devuelve filas aleatorias del batch actual para el grupo indicado. "
        "El batch cambia cada MIN_UPDATE_TIME segundos. Para una muestra minima, "
        "extrae al menos una porcion de cada uno de los 10 batches."
    ),
    response_model=BatchResponse,
    responses={
        400: {"description": "Numero de grupo invalido o se alcanzo la recoleccion minima por grupo."},
    },
)
def read_data(
    group_number: int = Query(..., ge=1, le=11, description="Numero de grupo asignado (1-10).", examples=[1])
):
    with connect() as conn:
        # FOR UPDATE: dos peticiones simultaneas del mismo grupo no avanzan el batch dos veces.
        last_update, batch = conn.execute(
            "SELECT last_update, batch FROM group_state WHERE group_number = %s FOR UPDATE",
            (group_number,),
        ).fetchone()

        # Verificar si el numero de conteo es adecuado
        if batch >= 11:
            raise HTTPException(status_code=400, detail="Ya se recolectó toda la información minima necesaria")

        current_time = time.time()
        # Verificar si han pasado mas de MIN_UPDATE_TIME desde la ultima actualizacion
        if current_time - last_update > MIN_UPDATE_TIME:
            last_update = current_time
            batch += 2 if batch == -1 else 1
            conn.execute(
                "UPDATE group_state SET last_update = %s, batch = %s WHERE group_number = %s",
                (last_update, batch, group_number),
            )

        # Igual que el original: el rango sale del numero de grupo, no del batch.
        random_data = get_batch_data(conn, group_number, batch_size)

    return {"group_number": group_number, "batch_number": batch, "data": random_data}


@app.get(
    "/restart_data_generation",
    tags=["admin"],
    summary="Reiniciar la generacion para un grupo",
    description=(
        "Reinicia el temporizador y el conteo de batch para el grupo indicado. "
        "Util para pruebas locales o para volver a comenzar la recoleccion de datos de un grupo."
    ),
)
def restart_data(
    group_number: int = Query(..., ge=1, le=11, description="Numero de grupo a reiniciar (1-10).", examples=[1])
):
    with connect() as conn:
        conn.execute(
            "UPDATE group_state SET last_update = 0, batch = -1 WHERE group_number = %s",
            (group_number,),
        )
    return {"ok"}
