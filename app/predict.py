from datetime import datetime, timedelta
from typing import Sequence, Optional
import math


def weibull_reliability(delta_seconds: float, eta: float, beta: float) -> float:
    # delta_seconds és eta ugyanabban a mértékegységben: másodpercet használunk
    if eta <= 0 or beta <= 0:
        return 0.5
    return math.exp(-((delta_seconds / eta) ** beta))


def predict_reliability(
    prediction_future_time: datetime,
    failure_start_time: datetime,
    maintenance_end_time: datetime,
    source_sys_time: datetime,
    eta_value: Optional[float] = None,
    beta_value: Optional[float] = None,
    default_reliability: Optional[Sequence[float]] = None,
) -> float:
    """
    Ha van eta/beta: Weibull megbízhatóság a maintenance_end_time → prediction_future_time horizonton.
    Ha nincs: fallback a default_reliability átlagára (vagy 0.9).
    """
    horizon = max(0.0, (prediction_future_time - maintenance_end_time).total_seconds())
    if eta_value and beta_value:
        rel = weibull_reliability(horizon, eta_value, beta_value)
        return round(max(0.0, min(1.0, rel)), 6)
    # Fallback
    base = sum(default_reliability) / len(default_reliability) if default_reliability else 0.9
    return round(max(0.0, min(1.0, base)), 6)


def compute_prediction_future_time(maintenance_end_time: datetime, days_ahead: int = 7) -> datetime:
    return maintenance_end_time + timedelta(days=days_ahead)
