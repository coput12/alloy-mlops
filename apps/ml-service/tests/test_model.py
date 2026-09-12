import os

import pytest
from app.model import ModelService

MODEL_PATH = os.getenv("MODEL_PATH", "models/model_rf.pkl")


@pytest.fixture(scope="module")
def model():
    svc = ModelService(path=MODEL_PATH)
    svc.load()
    return svc


def test_model_loads(model):
    assert model.ready is True
    assert model.version


def test_predict_single(model):
    # Чистое железо: 100% Fe, при 25C, растяжение
    prediction = model.predict([100.0, 0.0, 0.0, 0.0, 0.0, 25.0, 1])
    assert 0 <= prediction <= 3000


def test_predict_batch(model):
    rows = [
        [20.0, 20.0, 20.0, 20.0, 20.0, 25.0, 1],
        [10.0, 20.0, 30.0, 20.0, 20.0, 25.0, 0],
    ]
    values = model.predict_batch(rows)
    assert len(values) == 2
    assert all(0 <= v <= 3000 for v in values)


def test_is_tensile_changes_result(model):
    common = [20.0, 20.0, 20.0, 20.0, 20.0]
    tension = model.predict(common + [25.0, 1])
    compression = model.predict(common + [25.0, 0])
    assert tension != compression