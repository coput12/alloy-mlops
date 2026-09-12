from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter("ml_http_requests_total", "HTTP requests", ["method", "path", "status"])
PREDICTIONS = Counter("ml_predictions_total", "Predictions made", ["kind"])
LATENCY = Histogram("ml_predict_latency_seconds", "Predict latency", ["kind"])
MODEL_INFO = Gauge("ml_model_info", "Model version", ["version"])
PREDICT_VALUE = Histogram("ml_prediction_value", "Predicted UTS value", ["kind"])


def render_metrics():
    return generate_latest().decode("utf-8"), CONTENT_TYPE_LATEST


def set_model_info(version: str) -> None:
    MODEL_INFO.labels(version=version).set(1)