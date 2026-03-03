from datetime import datetime, timedelta
from typing import Sequence, Optional, List
import math
import random


def weibull_reliability(delta_seconds: float, eta: float, beta: float) -> float:
    # delta_seconds és eta ugyanabban a mértékegységben: másodpercet használunk
    if eta <= 0 or beta <= 0:
        return 0.5
    return math.exp(-((delta_seconds / eta) ** beta))


def predict(
    asset_id: int,
    prediction_future_time: datetime,
    failure_start_time: Optional[datetime],
    maintenance_end_time: datetime,
    source_sys_time: datetime,
    operation_ids: List[int],
    failure_type_ids: Optional[List[int]] = None,
    eta_value: Optional[float] = None,
    beta_value: Optional[float] = None,
    default_reliability: Optional[Sequence[float]] = None,
) -> float:
    """
    Ha van eta/beta: Weibull megbízhatóság a maintenance_end_time → prediction_future_time horizonton.
    Ha nincs: fallback a default_reliability átlagára (vagy 0.9).
    """
    count = len(failure_type_ids)
    if count == 0:
        return {"failure_type_probability": [], "predicted_reliability": 1.0}

    raw = [random.random() for _ in range(count)]
    raw_sum = sum(raw) or 1.0
    target_sum = random.random()

    failure_type_probability = [target_sum * (r / raw_sum) for r in raw]
    predicted_reliability = 1.0 - sum(failure_type_probability)

    return {"failure_type_ids": failure_type_ids, "failure_type_probability": failure_type_probability, "predicted_reliability": predicted_reliability}


def compute_prediction_future_time(maintenance_end_time: datetime, days_ahead: int = 7) -> datetime:
    return maintenance_end_time + timedelta(days=days_ahead)
