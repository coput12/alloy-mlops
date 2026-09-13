
COMPONENTS = ["Fe", "Co", "Ni", "Al", "Ti"]
SUM_TOLERANCE = 0.5


def _component_value(row: dict[str, float], k: str) -> float:
    return float(row.get(k, row.get(k.lower(), 0.0)))


def normalize_composition(row: dict[str, float]) -> dict[str, float]:
    """Приводит концентрации к сумме 100% (признаки модели строились так).

    Регистронезависимый разбор: клиенты присылают "fe", модель обучена на "Fe".
    """
    total = sum(_component_value(row, k) for k in COMPONENTS)
    if total <= 0:
        raise ValueError("Сумма концентраций должна быть больше нуля")
    return {k: _component_value(row, k) / total * 100.0 for k in COMPONENTS}


def sum_warning(row: dict[str, float]) -> str | None:
    total = sum(_component_value(row, k) for k in COMPONENTS)
    if abs(total - 100.0) > SUM_TOLERANCE:
        return f"Сумма компонентов = {total:.1f}%, будет нормализована до 100%"
    return None


def build_features(
    fe: float, co: float, ni: float, al: float, ti: float,
    t_test_c: float = 25.0, is_tensile: int = 1,
) -> list[float]:
    """Порядок фичей совпадает с обучением: Fe, Co, Ni, Al, Ti, T_test_C, IsTensile."""
    return [float(fe), float(co), float(ni), float(al), float(ti),
            float(t_test_c), int(is_tensile)]


def row_to_features(row: dict[str, float], t_test_c: float = 25.0, is_tensile: int = 1) -> list[float]:
    norm = normalize_composition(row)
    return build_features(norm["Fe"], norm["Co"], norm["Ni"], norm["Al"], norm["Ti"],
                          t_test_c, is_tensile)