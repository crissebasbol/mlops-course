#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v etl_pw="$AIRFLOW_ETL_PASSWORD" -v api_pw="$API_WRITER_PASSWORD" <<'SQL'
CREATE ROLE airflow_etl LOGIN PASSWORD :'etl_pw';
CREATE ROLE api_writer LOGIN PASSWORD :'api_pw';
SQL
