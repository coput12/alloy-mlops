from typing import Dict, List, Optional

COMPONENTS = ["Fe", "Co", "Ni", "Al", "Ti"]
SUM_TOLERANCE = 0.5


def normalize_composition(row: Dict[str, float]) -> Dict[str, float]:
    """Приводит концентрации к сумме 100% (признаки модели строились так)."""
    total = sum(float(row.get(k, 0.0)) for k in COMPONENTS)
    if total <= 0:
        raise ValueError("Сумма концентраций должна быть больше нуля")
    return {k: float(row.get(k, 0.0)) / total * 100.0 for k in COMPONENTS}


def sum_warning(row: Dict[str, float]) -> Optional[str]:
    total = sum(float(row.get(k, 0.0)) for k in COMPONENTS)
    if abs(total - 100.0) > SUM_TOLERANCE:
        return f"Сумма компонентов = {total:.1f}%, будет нормализована до 100%"
    return None


def build_features(
    fe: float, co: float, ni: float, al: float, ti: float,
    t_test_c: float = 25.0, is_tensile: int = 1,
) -> List[float]:
    """Порядок фичей совпадает с обучением: Fe, Co, Ni, Al, Ti, T_test_C, IsTensile."""
    return [float(fe), float(co), float(ni), float(al), float(ti),
            float(t_test_c), int(is_tensile)]


def row_to_features(row: Dict[str, float], t_test_c: float = 25.0, is_tensile: int = 1) -> List[float]:
    norm = normalize_composition(row)
    return build_features(norm["Fe"], norm["Co"], norm["Ni"], norm["Al"], norm["Ti"],
                          t_test_c, is_tensile)