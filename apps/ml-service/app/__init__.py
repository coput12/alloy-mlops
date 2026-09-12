from flask import Flask

from .api import api, init_model
from .config import Config
from .metrics import set_model_info
from .model import ModelService


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    service = ModelService()
    service.load()
    init_model(service)
    if service.ready:
        set_model_info(service.version)

    app.register_blueprint(api)

    @app.get("/")
    def index():
        return {
            "service": "alloy-mlops",
            "docs": {
                "health": "/health",
                "metrics": "/metrics",
                "predict": "/predict",
                "predict-batch": "/predict-batch",
                "tasks": "/tasks/<task_id>",
            },
        }

    return app