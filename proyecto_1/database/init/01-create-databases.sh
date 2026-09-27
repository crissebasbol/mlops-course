#!/bin/bash
# Crea las dos bases de datos de la instancia de datos
set -euo pipefail

crear_base() {
    local db="$1" usuario="$2" clave="$3"
    echo "Creando base de datos '${db}' con usuario '${usuario}'"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        CREATE USER ${usuario} WITH PASSWORD '${clave}';
        CREATE DATABASE ${db} OWNER ${usuario};
EOSQL
}

crear_base "$SOURCE_DB_NAME" "$SOURCE_DB_USER" "$SOURCE_DB_PASSWORD"
crear_base "$COVERTYPE_DB_NAME" "$COVERTYPE_DB_USER" "$COVERTYPE_DB_PASSWORD"
