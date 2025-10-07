from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import List, Optional
from uuid import UUID


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


class AssetFailureTypePredictIn(BaseModel):
    operation_ids: List[int] = Field(min_length=1)  # a maintenance műveletekhez
    failure_start_time: datetime
    maintenance_end_time: datetime
    source_sys_time: datetime
    asset_id: str = Field(min_length=1)
    # A predikcióhoz szükséges lehet:
    failure_type_id: Optional[int] = None
    default_reliability: Optional[List[float]] = None


class AssetFailureTypePredictOut(BaseModel):
    prediction_id: str


class Failures(BaseModel):
    failure_id: UUID  # a maintenance műveletekhez
    failure_name: str = Field(min_length=1)
    failure_type_id: UUID
    source_sys_time: datetime
    failure_start_time: datetime
    maintenance_end_time: datetime
