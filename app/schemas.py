from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class AssetPredictIn(BaseModel):
    operation_ids: List[int] = Field(min_length=1)  # a maintenance műveletekhez
    failure_start_time: datetime
    maintenance_end_time: datetime
    source_sys_time: datetime
    asset_id: str = Field(min_length=1)
    # A predikcióhoz szükséges lehet:
    failure_type_id: Optional[int] = None
    default_reliability: Optional[List[float]] = None  # ha nincs eta/beta


class AssetPredictOut(BaseModel):
    prediction_id: str
