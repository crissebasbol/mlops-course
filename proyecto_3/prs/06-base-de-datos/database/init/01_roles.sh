#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v etl_pw="$AIRFLOW_ETL_PASSWORD" \
  -v api_pw="$API_WRITER_PASSWORD" \
  -v reader_pw="$APP_READER_PASSWORD" <<'SQL'
CREATE ROLE airflow_etl LOGIN PASSWORD :'etl_pw';
CREATE ROLE api_writer LOGIN PASSWORD :'api_pw';
CREATE ROLE app_reader LOGIN PASSWORD :'reader_pw';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE housing TO airflow_etl, api_writer, app_reader;
SQL
