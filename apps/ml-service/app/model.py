import os
import pickle

from .config import Config


class ModelService:
    """Ленивая загрузка pickle-модели и предсказание."""

    def __init__(self, path: str | None = None, version: str | None = None):
        self.path = path or Config.MODEL_PATH
        self.version = version or Config.MODEL_VERSION
        self._model = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if not os.path.exists(self.path):
            self._model = None
            return
        with open(self.path, "rb") as f:
            self._model = pickle.load(f)
        self.version = Config.MODEL_VERSION if not self.version or self.version == "rf-v1" else self.version

    def predict(self, features: list[float]) -> float:
        if not self.ready:
            raise RuntimeError("Модель не загружена")
        value = float(self._model.predict([features])[0])
        if value < 0:
            value = 0.0
        return value

    def predict_batch(self, rows: list[list[float]]) -> list[float]:
        if not self.ready:
            raise RuntimeError("Модель не загружена")
        values = [max(float(x), 0.0) for x in self._model.predict(rows)]
        return values