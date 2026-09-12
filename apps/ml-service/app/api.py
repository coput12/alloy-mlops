import logging
import time

from flask import Blueprint, Response, jsonify, request

from . import metrics as m
from .config import Config
from .features import COMPONENTS, row_to_features, sum_warning
from .model import ModelService
from .tasks import cache_get, cache_set, get_task, publish_batch

log = logging.getLogger(__name__)

api = Blueprint("api", __name__)
model: ModelService = None


def init_model(service: ModelService) -> None:
    global model
    model = service


@api.get("/health")
def health():
    return jsonify({
        "status": "ok" if model.ready else "degraded",
        "model_ready": model.ready,
        "model_version": model.version if model.ready else None,
    })


@api.get("/metrics")
def metrics():
    data, ctype = m.render_metrics()
    return Response(data, mimetype=ctype)


@api.post("/predict")
def predict():
    if not model.ready:
        return jsonify({"error": "модель не загружена"}), 503

    body = request.get_json(silent=True) or {}
    start = time.perf_counter()
    try:
        if isinstance(body, list):
            if len(body) != 7:
                return jsonify({"error": "передайте список из 7 признаков или словарь состава"}), 422
            features = [float(x) for x in body]
            warning = None
        else:
            row = {k: body.get(k, body.get(k.lower())) for k in COMPONENTS}
            missing = [k for k in COMPONENTS if row.get(k) is None]
            if missing:
                return jsonify({"error": f"отсутствуют компоненты: {missing}"}), 422
            warning = sum_warning(row)
            features = row_to_features(
                row,
                t_test_c=float(body.get("t_test_c", Config.DEFAULT_TEMP)),
                is_tensile=int(body.get("is_tensile", 1)),
            )

        cache_key = ":".join(f"{x:.3f}" for x in features)
        cached = cache_get(cache_key)
        if cached is not None:
            prediction = cached["prediction"]
        else:
            prediction = model.predict(features)
            cache_set(cache_key, {"prediction": prediction})

        m.PREDICTIONS.labels(kind="sync").inc()
        m.PREDICT_VALUE.labels(kind="sync").observe(prediction)
        m.LATENCY.labels(kind="sync").observe(time.perf_counter() - start)
        return jsonify({
            "prediction": round(prediction, 1),
            "model_version": model.version,
            "warning": warning,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception:
        log.exception("predict failed")
        return jsonify({"error": "внутренняя ошибка"}), 500


@api.post("/predict-batch")
def predict_batch():
    body = request.get_json(silent=True) or {}
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        return jsonify({"error": "передайте непустой список rows"}), 422

    t_test_c = float(body.get("t_test_c", Config.DEFAULT_TEMP))
    is_tensile = int(body.get("is_tensile", 1))
    try:
        task_id = publish_batch(rows, t_test_c, is_tensile)
    except Exception:
        log.exception("rabbitmq недоступен")
        return jsonify({"error": "очередь задач недоступна"}), 503
    return jsonify({"task_id": task_id, "status": "queued"}), 202


@api.get("/tasks/<task_id>")
def task_status(task_id):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "задача не найдена или истёк TTL"}), 404
    return jsonify(task)