from pathlib import Path

import pytest
from app import create_app

DATA_CSV = Path(__file__).resolve().parents[3] / "data" / "alloy_data.csv"


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["model_ready"] is True


def test_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "ml_model_info" in resp.get_data(as_text=True)


def test_predict_dict(client):
    resp = client.post("/predict", json={
        "fe": 20, "co": 20, "ni": 20, "al": 20, "ti": 20,
        "is_tensile": 1,
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert 0 < body["prediction"] < 3000


def test_predict_list(client):
    resp = client.post("/predict", json=[20, 20, 20, 20, 20, 25.0, 1])
    assert resp.status_code == 200


def test_predict_missing_columns(client):
    resp = client.post("/predict", json={"fe": 50, "co": 50})
    assert resp.status_code == 422


def test_predict_invalid_length(client):
    resp = client.post("/predict", json=[1, 2, 3])
    assert resp.status_code == 422


@pytest.mark.parametrize("index", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_sample_alloys_predict(client, index):
    """Прогон по реальным составам из датасета (первые 10 строк)."""
    import pandas as pd

    df = pd.read_csv(DATA_CSV, nrows=10)
    row = df.iloc[index]
    resp = client.post("/predict", json={
        "fe": float(row["Fe"]),
        "co": float(row["Co"]),
        "ni": float(row["Ni"]),
        "al": float(row["Al"]),
        "ti": float(row["Ti"]),
        "t_test_c": float(row["T_test_C"]),
        "is_tensile": int(row["IsTensile"]),
    })
    assert resp.status_code == 200
    predicted = resp.get_json()["prediction"]
    assert abs(predicted - float(row["UTS_MPa"])) < 600


def test_batch_accepted(client, monkeypatch):
    """Без живой очереди проверяем только валидацию и 202."""
    import sys

    api_module = sys.modules["app.api"]
    monkeypatch.setattr(api_module, "publish_batch", lambda rows, t, i: "test-task-id")
    resp = client.post("/predict-batch", json={
        "rows": [{"fe": 20, "co": 20, "ni": 20, "al": 20, "ti": 20}],
    })
    assert resp.status_code == 202
    assert resp.get_json()["task_id"] == "test-task-id"


def test_batch_empty_rejected(client):
    resp = client.post("/predict-batch", json={"rows": []})
    assert resp.status_code == 422