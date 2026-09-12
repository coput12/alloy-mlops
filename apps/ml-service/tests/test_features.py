import pytest
from app.features import (
    build_features,
    normalize_composition,
    row_to_features,
    sum_warning,
)


def test_normalize_to_100():
    row = {"Fe": 20, "Co": 20, "Ni": 20, "Al": 20, "Ti": 20}
    norm = normalize_composition(row)
    assert sum(norm.values()) == pytest.approx(100.0)


def test_normalize_partial():
    row = {"Fe": 10, "Co": 20, "Ni": 30, "Al": 0, "Ti": 0}
    norm = normalize_composition(row)
    assert sum(norm.values()) == pytest.approx(100.0)
    assert norm["Fe"] == pytest.approx(100 / 6)


def test_zero_sum_raises():
    with pytest.raises(ValueError):
        normalize_composition({"Fe": 0, "Co": 0, "Ni": 0, "Al": 0, "Ti": 0})


def test_build_features_length():
    features = build_features(20, 20, 20, 20, 20, 25.0, 1)
    assert len(features) == 7
    assert features[-2] == 25.0
    assert features[-1] == 1


def test_row_to_features():
    row = {"Fe": 25, "Co": 25, "Ni": 25, "Al": 25, "Ti": 0}
    feat = row_to_features(row, t_test_c=25.0, is_tensile=0)
    assert feat[0] + feat[1] + feat[2] + feat[3] == pytest.approx(100.0)


def test_sum_warning_none_at_100():
    assert sum_warning({"Fe": 50, "Co": 50, "Ni": 0, "Al": 0, "Ti": 0}) is None


def test_sum_warning_present():
    assert sum_warning({"Fe": 30, "Co": 30, "Ni": 30, "Al": 0, "Ti": 0}) is not None