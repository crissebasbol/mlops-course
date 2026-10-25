from prometheus_client import Counter, Gauge, Histogram

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 10)

HTTP_REQUESTS = Counter(
    "http_requests_total", "Peticiones HTTP atendidas", ["method", "endpoint", "status"]
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "Latencia de las peticiones HTTP", ["method", "endpoint"],
    buckets=LATENCY_BUCKETS,
)
HTTP_IN_PROGRESS = Gauge("http_requests_in_progress", "Peticiones en curso")

PREDICTIONS = Counter("predictions_total", "Predicciones por clase", ["prediction_label", "model_version"])
PREDICTION_ERRORS = Counter("prediction_errors_total", "Errores en /predict", ["reason"])
INFERENCE_LATENCY = Histogram(
    "model_inference_duration_seconds", "Tiempo de predict_proba del modelo", buckets=LATENCY_BUCKETS
)
INFERENCE_LOG_LATENCY = Histogram(
    "inference_log_duration_seconds", "Tiempo de insertar la inferencia en Postgres", buckets=LATENCY_BUCKETS
)

MODEL_INFO = Gauge("model_info", "Modelo cargado en memoria (valor 1)", ["model_name", "model_version", "alias"])
MODEL_RELOADS = Counter("model_reloads_total", "Cargas del modelo desde MLflow")
