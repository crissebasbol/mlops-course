#!/bin/bash
# Crea la base de datos de covertype con su propio usuario
set -euo pipefail

echo "Creando base de datos '${COVERTYPE_DB_NAME}' con usuario '${COVERTYPE_DB_USER}'"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER ${COVERTYPE_DB_USER} WITH PASSWORD '${COVERTYPE_DB_PASSWORD}';
    CREATE DATABASE ${COVERTYPE_DB_NAME} OWNER ${COVERTYPE_DB_USER};
EOSQL
