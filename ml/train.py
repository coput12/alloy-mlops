"""Пайплайн обучения модели прочности сплавов Fe-Co-Ni-Al-Ti.

Запускается: локально, в GitHub Actions (ночной ретрейн), в GitLab CI.
Выход: models/model_rf.pkl + ml/artifacts/metrics.json

Пример: python ml/train.py --data data/alloy_data.csv --out models/model_rf.pkl
"""
import argparse
import json
import os
import pickle
import warnings
from dataclasses import asdict, dataclass

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402
from sklearn.model_selection import KFold, cross_val_score  # noqa: E402

FEATURES = ["Fe", "Co", "Ni", "Al", "Ti", "T_test_C", "IsTensile"]
TARGET = "UTS_MPa"


@dataclass
class Metrics:
    n_records: int
    cv_r2_mean: float
    cv_r2_std: float
    train_r2: float
    train_mae: float
    tension_r2: float
    tension_mae: float
    compression_r2: float
    compression_mae: float


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "IsTensile" not in df.columns and "Test_Type" in df.columns:
        df["IsTensile"] = (df["Test_Type"] == "T").astype(int)
    return df.dropna(subset=FEATURES + [TARGET])


def train(df: pd.DataFrame, n_estimators: int, max_depth: int) -> tuple[RandomForestRegressor, Metrics]:
    X = df[FEATURES].values
    y = df[TARGET].values

    rf = RandomForestRegressor(
        n_estimators=n_estimators, max_depth=max_depth,
        min_samples_leaf=2, random_state=42, n_jobs=-1,
    )
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv = cross_val_score(rf, X, y, cv=kf, scoring="r2")

    rf.fit(X, y)
    y_pred = rf.predict(X)

    t_mask = df["Test_Type"] == "T"
    c_mask = df["Test_Type"] == "C"

    metrics = Metrics(
        n_records=len(df),
        cv_r2_mean=float(cv.mean()),
        cv_r2_std=float(cv.std()),
        train_r2=float(r2_score(y, y_pred)),
        train_mae=float(mean_absolute_error(y, y_pred)),
        tension_r2=float(r2_score(df.loc[t_mask, TARGET], rf.predict(df.loc[t_mask, FEATURES]))),
        tension_mae=float(mean_absolute_error(df.loc[t_mask, TARGET], rf.predict(df.loc[t_mask, FEATURES]))),
        compression_r2=float(r2_score(df.loc[c_mask, TARGET], rf.predict(df.loc[c_mask, FEATURES]))),
        compression_mae=float(mean_absolute_error(df.loc[c_mask, TARGET], rf.predict(df.loc[c_mask, FEATURES]))),
    )
    return rf, metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.getenv("DATA_PATH", "data/alloy_data.csv"))
    ap.add_argument("--out", default=os.getenv("MODEL_OUT_PATH", "models/model_rf.pkl"))
    ap.add_argument("--metrics-out", default="ml/artifacts/metrics.json")
    ap.add_argument("--n-estimators", type=int, default=int(os.getenv("RF_N_ESTIMATORS", "300")))
    ap.add_argument("--max-depth", type=int, default=10)
    args = ap.parse_args()

    df = load_data(args.data)
    model, metrics = train(df, args.n_estimators, args.max_depth)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "wb") as f:
        pickle.dump(model, f)

    os.makedirs(os.path.dirname(args.metrics_out) or ".", exist_ok=True)
    with open(args.metrics_out, "w", encoding="utf-8") as f:
        json.dump(asdict(metrics), f, indent=2)

    report = (
        f"\n=== ОБУЧЕНИЕ ЗАВЕРШЕНО ===\n"
        f"Записей: {metrics.n_records}\n"
        f"CV R²: {metrics.cv_r2_mean:.3f} ± {metrics.cv_r2_std:.3f}\n"
        f"Train R²: {metrics.train_r2:.3f}, MAE: {metrics.train_mae:.0f} МПа\n"
        f"Растяжение: R²={metrics.tension_r2:.3f}, MAE={metrics.tension_mae:.0f}\n"
        f"Сжатие:     R²={metrics.compression_r2:.3f}, MAE={metrics.compression_mae:.0f}\n"
        f"Модель: {args.out}\nМетрики: {args.metrics_out}"
    )
    print(report)


if __name__ == "__main__":
    main()