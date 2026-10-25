-- Capas de datos de la base `diabetes`:
--   raw        datos tal como llegan del CSV (Airflow escribe)
--   clean      datos limpios listos para entrenar (Airflow escribe)
--   inference  registro de cada prediccion de la API (API escribe, Airflow solo lee)

CREATE SCHEMA raw AUTHORIZATION airflow_etl;
CREATE SCHEMA clean AUTHORIZATION airflow_etl;
CREATE SCHEMA inference AUTHORIZATION api_writer;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

SET ROLE airflow_etl;

CREATE TABLE raw.batches (
    batch_id        INTEGER PRIMARY KEY,
    source_file     TEXT NOT NULL,
    row_start       INTEGER NOT NULL,
    row_end         INTEGER NOT NULL,
    rows_in_file    INTEGER,
    rows_inserted   INTEGER,
    rows_valid      INTEGER,
    rows_rejected   INTEGER,
    rows_clean      INTEGER,
    status          TEXT NOT NULL CHECK (status IN ('loading', 'loaded', 'validated', 'processed', 'failed')),
    dag_run_id      TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (row_end - row_start <= 15000)
);

CREATE TABLE raw.diabetes (
    row_hash                 CHAR(32) PRIMARY KEY,
    batch_id                 INTEGER NOT NULL REFERENCES raw.batches (batch_id),
    source_file              TEXT NOT NULL,
    source_row               INTEGER NOT NULL,
    load_timestamp           TIMESTAMPTZ NOT NULL DEFAULT now(),
    status                   TEXT NOT NULL DEFAULT 'loaded'
                             CHECK (status IN ('loaded', 'valid', 'rejected', 'excluded', 'processed')),
    status_reason            TEXT,
    encounter_id             TEXT,
    patient_nbr              TEXT,
    race                     TEXT,
    gender                   TEXT,
    age                      TEXT,
    weight                   TEXT,
    admission_type_id        TEXT,
    discharge_disposition_id TEXT,
    admission_source_id      TEXT,
    time_in_hospital         TEXT,
    payer_code               TEXT,
    medical_specialty        TEXT,
    num_lab_procedures       TEXT,
    num_procedures           TEXT,
    num_medications          TEXT,
    number_outpatient        TEXT,
    number_emergency         TEXT,
    number_inpatient         TEXT,
    diag_1                   TEXT,
    diag_2                   TEXT,
    diag_3                   TEXT,
    number_diagnoses         TEXT,
    max_glu_serum            TEXT,
    a1cresult                TEXT,
    metformin                TEXT,
    repaglinide              TEXT,
    nateglinide              TEXT,
    chlorpropamide           TEXT,
    glimepiride              TEXT,
    acetohexamide            TEXT,
    glipizide                TEXT,
    glyburide                TEXT,
    tolbutamide              TEXT,
    pioglitazone             TEXT,
    rosiglitazone            TEXT,
    acarbose                 TEXT,
    miglitol                 TEXT,
    troglitazone             TEXT,
    tolazamide               TEXT,
    examide                  TEXT,
    citoglipton              TEXT,
    insulin                  TEXT,
    glyburide_metformin      TEXT,
    glipizide_metformin      TEXT,
    glimepiride_pioglitazone TEXT,
    metformin_rosiglitazone  TEXT,
    metformin_pioglitazone   TEXT,
    change                   TEXT,
    diabetesmed              TEXT,
    readmitted               TEXT
);
CREATE INDEX raw_diabetes_batch_status_idx ON raw.diabetes (batch_id, status);

CREATE TABLE clean.diabetes (
    row_hash               CHAR(32) PRIMARY KEY REFERENCES raw.diabetes (row_hash),
    batch_id               INTEGER NOT NULL,
    encounter_id           BIGINT NOT NULL,
    patient_nbr            BIGINT NOT NULL,
    split                  TEXT NOT NULL CHECK (split IN ('train', 'val', 'test')),
    time_in_hospital       INTEGER NOT NULL,
    num_lab_procedures     INTEGER NOT NULL,
    num_procedures         INTEGER NOT NULL,
    num_medications        INTEGER NOT NULL,
    number_outpatient      INTEGER NOT NULL,
    number_emergency       INTEGER NOT NULL,
    number_inpatient       INTEGER NOT NULL,
    number_diagnoses       INTEGER NOT NULL,
    diabetes_meds_active   INTEGER NOT NULL,
    diabetes_meds_changed  INTEGER NOT NULL,
    age                    TEXT NOT NULL,
    race                   TEXT NOT NULL,
    gender                 TEXT NOT NULL,
    admission_type         TEXT NOT NULL,
    discharge_disposition  TEXT NOT NULL,
    admission_source       TEXT NOT NULL,
    medical_specialty      TEXT NOT NULL,
    diag_1_group           TEXT NOT NULL,
    diag_2_group           TEXT NOT NULL,
    diag_3_group           TEXT NOT NULL,
    max_glu_serum          TEXT NOT NULL,
    a1cresult              TEXT NOT NULL,
    metformin              TEXT NOT NULL,
    glipizide              TEXT NOT NULL,
    glyburide              TEXT NOT NULL,
    pioglitazone           TEXT NOT NULL,
    rosiglitazone          TEXT NOT NULL,
    glimepiride            TEXT NOT NULL,
    insulin                TEXT NOT NULL,
    change                 TEXT NOT NULL,
    diabetesmed            TEXT NOT NULL,
    readmitted             TEXT NOT NULL,
    target                 SMALLINT NOT NULL CHECK (target IN (0, 1, 2)),
    processed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX clean_diabetes_split_idx ON clean.diabetes (split);
CREATE INDEX clean_diabetes_batch_idx ON clean.diabetes (batch_id);

RESET ROLE;

SET ROLE api_writer;

CREATE TABLE inference.predictions (
    request_id        UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    input             JSONB NOT NULL,
    prediction        SMALLINT NOT NULL,
    prediction_label  TEXT NOT NULL,
    probability       DOUBLE PRECISION,
    probabilities     JSONB,
    model_name        TEXT NOT NULL,
    model_version     INTEGER NOT NULL,
    model_alias       TEXT NOT NULL,
    latency_ms        DOUBLE PRECISION NOT NULL,
    api_replica       TEXT
);
CREATE INDEX inference_predictions_created_idx ON inference.predictions (created_at);

GRANT USAGE ON SCHEMA inference TO airflow_etl;
GRANT SELECT ON inference.predictions TO airflow_etl;

RESET ROLE;
