from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class AssetPredictIn(BaseModel):
    operation_ids: List[int]
    failure_start_time: datetime
    maintenance_end_time: datetime
    source_sys_time: datetime
    asset_id: int
    default_reliability: Optional[List[float]] = None


class AssetPredictOut(BaseModel):
    prediction_id: int


class AssetFailureTypePredictIn(BaseModel):
    operation_ids: List[int]
    failure_start_time: datetime
    maintenance_end_time: datetime
    source_sys_time: datetime
    asset_id: int
    failure_type_ids: List[int]
    default_reliability: Optional[List[float]] = None


class AssetFailureTypePredictOut(BaseModel):
    prediction_id: int


class AssetIn(BaseModel):
    asset_id: int
    asset_name: str = Field(min_length=1)


class FailureTypeIn(BaseModel):
    failure_type_id: int
    failure_type_name: str = Field(min_length=1)
    is_preventive: bool


class MaintenanceListIn(BaseModel):
    maintenance_list_id: int
    maintenance_list_name: str = Field(min_length=1)


class OperationOut(BaseModel):
    operation_id: int
    type: str  # PREVENTIVE | CORRECTIVE | BOTH | UNKNOWN


class AssetFailureTypeOperationsOut(BaseModel):
    failure_type_id: int
    asset_id: int
    operations: List[OperationOut]
