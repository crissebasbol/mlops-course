#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v etl_secret="$AIRFLOW_ETL_PASSWORD" \
  -v api_secret="$API_WRITER_PASSWORD" \
  -v reader_secret="$APP_READER_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', role_name, secret)
FROM (VALUES
    ('airflow_etl', :'etl_secret'),
    ('api_writer', :'api_secret'),
    ('app_reader', :'reader_secret')
) AS roles (role_name, secret)
\gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE housing TO airflow_etl, api_writer, app_reader;
SQL
