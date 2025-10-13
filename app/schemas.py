from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class AssetPredictIn(BaseModel):
    operation_id: List[UUID]  # a maintenance műveletekhez
    failure_start_time: datetime
    maintenance_end_time: datetime
    source_sys_time: datetime
    asset_id: UUID
    # A predikcióhoz szükséges lehet:
    failure_type_id: Optional[UUID] = None
    default_reliability: Optional[List[float]] = None  # ha nincs eta/beta


class AssetPredictOut(BaseModel):
    prediction_id: UUID
    predicted_value: float


class AssetFailureTypePredictIn(BaseModel):
    operation_id: List[UUID]  # a maintenance műveletekhez
    failure_start_time: datetime
    maintenance_end_time: datetime
    source_sys_time: datetime
    asset_id: UUID
    # A predikcióhoz szükséges lehet:
    failure_type_id: Optional[UUID] = None
    default_reliability: Optional[List[float]] = None


class AssetFailureTypePredictOut(BaseModel):
    prediction_id: UUID


class Failures(BaseModel):
    failure_id: UUID  # a maintenance műveletekhez
    failure_name: str = Field(min_length=1)
    failure_type_id: UUID
    source_sys_time: datetime
    failure_start_time: datetime
    maintenance_end_time: datetime


class AssetIn(BaseModel):
    asset_id: UUID
    asset_name: str = Field(min_length=1)


class FailureTypeIn(BaseModel):
    failure_type_id: UUID
    failure_type_name: str = Field(min_length=1)
    is_preventive: bool


class MaintenanceListIn(BaseModel):
    maintenance_list_id: UUID
    maintenance_list_name: str = Field(min_length=1)
