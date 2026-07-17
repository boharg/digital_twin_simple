from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetPredictIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workorder_id: int = Field(gt=0)

    sf_asset_id: int = Field(alias="asset_id", gt=0)

    failure_cause_id: Optional[int] = Field(default=None, gt=0)

    failuredate: datetime
    ended: datetime

    type: str = Field(min_length=1)
    operation_ids: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_asset_predict(self):
        if self.ended < self.failuredate:
            raise ValueError("ended cannot be earlier than failuredate")

        if any(operation_id <= 0 for operation_id in self.operation_ids):
            raise ValueError("Every operation_id must be greater than zero")

        if (self.type.strip().upper() != "PREVENTIVE" and self.failure_cause_id is None):
            raise ValueError("failure_cause_id is required for a non-preventive work order")

        return self


class AssetPredictAccepted(BaseModel):
    job_id: int


class AssetPredictionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prediction_id: int = Field(gt=0)

    sf_asset_id: int = Field(serialization_alias="asset_id", gt=0)

    predicted_reliability: float = Field(ge=0.0, le=1.0)


class FailureCausePredictionItem(BaseModel):
    asset_failurecause_id: int = Field(gt=0)

    predicted_reliability: float = Field(ge=0.0, le=1.0)


class AssetFailureCausePredictionPayload(BaseModel):
    prediction_id: int = Field(gt=0)

    failure_causes: list[FailureCausePredictionItem] = Field(min_length=1)
