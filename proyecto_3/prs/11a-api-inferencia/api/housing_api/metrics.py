from prometheus_client import Counter, Gauge, Histogram

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

HTTP_REQUESTS = Counter("http_requests_total", "Peticiones HTTP", ["endpoint", "status"])
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "Duración de las peticiones",
    ["endpoint"],
    buckets=LATENCY_BUCKETS,
)
HTTP_IN_PROGRESS = Gauge("http_requests_in_progress", "Peticiones en curso", ["endpoint"])

PREDICTIONS = Counter("predictions_total", "Predicciones hechas", ["model_role"])
INFERENCE_SECONDS = Histogram(
    "model_inference_seconds",
    "Tiempo de predicción del modelo",
    ["model_role"],
    buckets=LATENCY_BUCKETS,
)
PREDICTION_ERRORS = Counter("prediction_errors_total", "Predicciones fallidas", ["reason"])
SHADOW_RELATIVE_DIFF = Histogram(
    "shadow_relative_diff",
    "Diferencia relativa entre sombra y champion",
    buckets=(0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0),
)
UNKNOWN_CATEGORY = Counter(
    "unknown_category_total", "Categorías que el champion no vio al entrenar", ["field"]
)

MODEL_INFO = Gauge("model_info", "Modelo cargado", ["version", "alias", "role"])
MODEL_RELOADS = Counter("model_reloads_total", "Cambios de modelo cargado", ["role"])
MODEL_RELOAD_FAILURES = Counter("model_reload_failures_total", "Recargas fallidas", ["role"])

INFERENCE_LOG_SECONDS = Histogram(
    "inference_log_seconds",
    "Escritura de un lote de eventos en Postgres",
    buckets=LATENCY_BUCKETS,
)
INFERENCE_LOG_ERRORS = Counter(
    "inference_log_errors_total", "Eventos de inferencia que no se guardaron", ["reason"]
)
INFERENCE_LOG_QUEUE = Gauge("inference_log_queue_size", "Eventos en cola para guardar")
