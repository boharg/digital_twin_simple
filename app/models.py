import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    String,
    Text,
    text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    not_found = "not_found"
    error = "error"


class PredictionJob(Base):
    __tablename__ = "prediction_jobs"

    job_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    workorder_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True,)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="jobstatus"), nullable=False, default=JobStatus.queued)
    endpoint_type: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    asset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sf_asset_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)


class FailureType(Base):
    __tablename__ = "failure_types"

    failure_type_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    failure_type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preventive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    failure_cause_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class AssetFailureType(Base):
    __tablename__ = "asset_failure_types"

    asset_failure_type_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    failure_type_id: Mapped[int | None] = mapped_column(ForeignKey("failure_types.failure_type_id"), nullable=True)
    default_occurrence_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    asset_failurecause_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Sensor(Base):
    __tablename__ = "sensors"

    sensor_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sensor_name: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    ranges_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    metric_function_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class EtaBeta(Base):
    __tablename__ = "etas_betas"

    eta_beta_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    eta_value: Mapped[float] = mapped_column(Float, nullable=False)
    beta_value: Mapped[float] = mapped_column(Float, nullable=False)

    asset_failure_type_id: Mapped[int] = mapped_column(ForeignKey("asset_failure_types.asset_failure_type_id"), nullable=False)
    learning_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AssetWorksheetList(Base):
    __tablename__ = "asset_worksheet_lists"

    asset_worksheet_list_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, autoincrement=True)
    maintenance_end_date: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    source_sys_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    asset_failure_type_id: Mapped[int | None] = mapped_column(ForeignKey("asset_failure_types.asset_failure_type_id"), nullable=True)
    failure_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downtime_in_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sys_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class OperationsDoneList(Base):
    __tablename__ = "operations_done_lists"

    operations_done_list_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    operation_template_id: Mapped[int] = mapped_column(BigInteger, nullable=False,)
    asset_worksheet_list_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    maintenance_end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            [
                "asset_worksheet_list_id",
                "maintenance_end_date",
            ],
            [
                "asset_worksheet_lists.asset_worksheet_list_id",
                "asset_worksheet_lists.maintenance_end_date",
            ],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    asset_failure_type_id: Mapped[int | None] = mapped_column(ForeignKey("asset_failure_types.asset_failure_type_id"), nullable=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("prediction_jobs.job_id"), nullable=False)


class PredictionAssetLevel(Base):
    __tablename__ = "prediction_asset_levels"

    prediction_asset_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, autoincrement=True)
    forecast_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.prediction_id"), nullable=False)
    nowcast_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    nowcast_virtual_age: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_virtual_age: Mapped[float] = mapped_column(Float, nullable=False)
    nowcast_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PredictionAssetFailureTypeLevel(Base):
    __tablename__ = "prediction_asset_failure_type_levels"

    prediction_asset_failure_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, autoincrement=True)
    forecast_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.prediction_id"), nullable=False)
    nowcast_failure_type_probability: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_failure_type_probability: Mapped[float] = mapped_column(Float, nullable=False)
    nowcast_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SensorFailureType(Base):
    __tablename__ = "sensor_failure_types"

    sensor_failure_type_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.sensor_id"), nullable=False)
    failure_type_id: Mapped[int] = mapped_column(ForeignKey("failure_types.failure_type_id"), nullable=False)


class SensorStatistic(Base):
    __tablename__ = "sensor_statistics"

    sensor_statistic_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.sensor_id"), nullable=False)
    standard_deviation_value: Mapped[float] = mapped_column(Float, nullable=False)
    average_value: Mapped[float] = mapped_column(Float, nullable=False)
    learning_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Gamma(Base):
    __tablename__ = "gammas"

    gamma_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    gamma_value: Mapped[float] = mapped_column(Float, nullable=False)
    sensor_failure_type_id: Mapped[int] = mapped_column(ForeignKey("sensor_failure_types.sensor_failure_type_id"), nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    learning_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
