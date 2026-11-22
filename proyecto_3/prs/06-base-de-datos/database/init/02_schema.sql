-- raw:   lotes tal como llegan de la API de datos y eventos de inferencia de la API
-- clean: filas validadas y normalizadas, listas para entrenar, trazables a su lote crudo
-- audit: historial de decisiones por lote, evaluaciones de modelos y acciones de operación

CREATE SCHEMA raw AUTHORIZATION airflow_etl;
CREATE SCHEMA clean AUTHORIZATION airflow_etl;
CREATE SCHEMA audit AUTHORIZATION airflow_etl;

SET ROLE airflow_etl;

CREATE TABLE raw.batches (
    ingestion_id          BIGSERIAL PRIMARY KEY,
    dag_run_id            TEXT NOT NULL,
    cycle                 INTEGER NOT NULL,
    api_batch_number      INTEGER,
    expected_batch_number INTEGER,
    group_number          INTEGER NOT NULL,
    day                   TEXT,
    requested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    http_status           INTEGER,
    outcome               TEXT NOT NULL
                          CHECK (outcome IN ('new', 'duplicate', 'empty', 'end_of_data')),
    record_count          INTEGER NOT NULL DEFAULT 0,
    data_sha256           CHAR(64),
    duplicate_of          BIGINT REFERENCES raw.batches (ingestion_id),
    landing_uri           TEXT,
    schema_received       JSONB,
    status                TEXT NOT NULL DEFAULT 'fetched'
                          CHECK (status IN ('fetched', 'stored', 'processed', 'failed',
                                            'quarantined', 'closed')),
    attempts              INTEGER NOT NULL DEFAULT 1,
    error                 TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX batches_new_data_sha256 ON raw.batches (data_sha256) WHERE outcome = 'new';
CREATE INDEX batches_status ON raw.batches (status);

CREATE TABLE raw.properties (
    ingestion_id    BIGINT NOT NULL REFERENCES raw.batches (ingestion_id),
    source_row      INTEGER NOT NULL,
    row_hash        CHAR(64) NOT NULL,
    payload         JSONB NOT NULL,
    quality_status  TEXT CHECK (quality_status IN ('valid', 'rejected')),
    quality_reasons TEXT[],
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ingestion_id, source_row)
);
CREATE INDEX properties_row_hash ON raw.properties (row_hash);

CREATE TABLE raw.inference_events (
    request_id          UUID PRIMARY KEY,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    traffic_source      TEXT NOT NULL DEFAULT 'api',
    endpoint            TEXT NOT NULL,
    request             JSONB,
    status_code         INTEGER NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('ok', 'invalid_input', 'no_model', 'error')),
    error               TEXT,
    model_name          TEXT,
    champion_version    INTEGER,
    prediction          DOUBLE PRECISION,
    champion_latency_ms DOUBLE PRECISION,
    shadow_version      INTEGER,
    shadow_prediction   DOUBLE PRECISION,
    shadow_latency_ms   DOUBLE PRECISION,
    replay_row_hash     CHAR(64)
);
CREATE INDEX inference_events_ts ON raw.inference_events (ts);
CREATE INDEX inference_events_source_ts ON raw.inference_events (traffic_source, ts);

CREATE TABLE raw.inference_feedback (
    id           BIGSERIAL PRIMARY KEY,
    request_id   UUID NOT NULL,
    actual_price DOUBLE PRECISION NOT NULL CHECK (actual_price > 0),
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source       TEXT NOT NULL DEFAULT 'api'
);
CREATE INDEX inference_feedback_request ON raw.inference_feedback (request_id);

CREATE TABLE clean.properties (
    row_hash              CHAR(64) PRIMARY KEY,
    ingestion_id          BIGINT NOT NULL REFERENCES raw.batches (ingestion_id),
    cycle                 INTEGER NOT NULL,
    api_batch_number      INTEGER NOT NULL,
    split                 TEXT NOT NULL CHECK (split IN ('train', 'val', 'test', 'holdout')),
    price                 DOUBLE PRECISION NOT NULL,
    bed                   DOUBLE PRECISION NOT NULL,
    bath                  DOUBLE PRECISION NOT NULL,
    acre_lot              DOUBLE PRECISION NOT NULL,
    house_size            DOUBLE PRECISION NOT NULL,
    prev_sold_date        DATE,
    status                TEXT NOT NULL,
    city                  TEXT NOT NULL,
    state                 TEXT NOT NULL,
    zip_code              CHAR(5) NOT NULL,
    brokered_by           TEXT,
    preprocessing_version TEXT NOT NULL,
    processed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX clean_properties_split ON clean.properties (split);
CREATE INDEX clean_properties_ingestion ON clean.properties (ingestion_id);

CREATE TABLE audit.batch_runs (
    ingestion_id            BIGINT PRIMARY KEY REFERENCES raw.batches (ingestion_id),
    dag_run_id              TEXT NOT NULL,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at             TIMESTAMPTZ,
    cycle                   INTEGER NOT NULL,
    api_batch_number        INTEGER,
    outcome                 TEXT NOT NULL,
    record_count            INTEGER,
    valid_rows              INTEGER,
    rejected_rows           INTEGER,
    schema_status           TEXT,
    schema_report           JSONB,
    quality_report          JSONB,
    new_categories          JSONB,
    drift_report            JSONB,
    champion_version_before INTEGER,
    champion_mape_on_batch  DOUBLE PRECISION,
    training_decision       TEXT CHECK (training_decision IN ('train', 'skip')),
    training_code           TEXT,
    training_signals        TEXT[],
    training_reason         TEXT,
    mlflow_run_id           TEXT,
    candidate_version       INTEGER,
    gates                   JSONB,
    diagnostics             JSONB,
    promotion_decision      TEXT CHECK (promotion_decision IN ('promoted', 'rejected')),
    promotion_reason        TEXT,
    mape_candidate          DOUBLE PRECISION,
    mape_champion           DOUBLE PRECISION,
    mape_delta_pct          DOUBLE PRECISION,
    mae_delta_pct           DOUBLE PRECISION,
    r2_delta                DOUBLE PRECISION,
    champion_version_after  INTEGER,
    final_status            TEXT NOT NULL DEFAULT 'running'
                            CHECK (final_status IN ('running', 'success', 'skipped', 'duplicate',
                                                    'no_data', 'failed')),
    error                   TEXT
);

CREATE TABLE audit.model_evaluations (
    id            BIGSERIAL PRIMARY KEY,
    ingestion_id  BIGINT REFERENCES raw.batches (ingestion_id),
    cycle         INTEGER,
    model_version INTEGER NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('champion', 'candidate', 'shadow')),
    dataset       TEXT NOT NULL,
    metric        TEXT NOT NULL,
    value         DOUBLE PRECISION NOT NULL,
    n_rows        INTEGER,
    evaluated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX model_evaluations_lookup ON audit.model_evaluations (dataset, metric, evaluated_at);

CREATE TABLE audit.model_actions (
    id           BIGSERIAL PRIMARY KEY,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    action       TEXT NOT NULL CHECK (action IN ('rollback', 'reload')),
    from_version INTEGER,
    to_version   INTEGER,
    actor        TEXT NOT NULL,
    reason       TEXT,
    source       TEXT NOT NULL DEFAULT 'api'
);

CREATE VIEW audit.replay_accuracy AS
SELECT
    date_trunc('minute', e.ts) AS minute,
    e.champion_version,
    e.shadow_version,
    count(*) AS requests,
    avg(abs(e.prediction - c.price) / c.price) AS champion_mape,
    avg(abs(e.shadow_prediction - c.price) / c.price)
        FILTER (WHERE e.shadow_prediction IS NOT NULL) AS shadow_mape
FROM raw.inference_events AS e
JOIN clean.properties AS c ON c.row_hash = e.replay_row_hash
WHERE e.traffic_source = 'replay' AND e.status = 'ok'
GROUP BY 1, 2, 3;

GRANT USAGE ON SCHEMA raw, audit TO api_writer;
GRANT INSERT ON raw.inference_events, raw.inference_feedback TO api_writer;
GRANT INSERT, SELECT ON audit.model_actions TO api_writer;
GRANT USAGE ON SEQUENCE raw.inference_feedback_id_seq, audit.model_actions_id_seq TO api_writer;

GRANT USAGE ON SCHEMA raw, audit TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA audit TO app_reader;
GRANT SELECT ON raw.batches, raw.inference_events, raw.inference_feedback TO app_reader;

RESET ROLE;
