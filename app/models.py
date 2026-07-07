from datetime import datetime
import enum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
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


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_name: Mapped[str | None] = mapped_column(Text)


class Range(Base):
    __tablename__ = "ranges"

    ranges_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    range_ok_upper: Mapped[float | None] = mapped_column(Float)
    range_ok_lower: Mapped[float | None] = mapped_column(Float)
    range_warn_upper: Mapped[float | None] = mapped_column(Float)
    range_warn_lower: Mapped[float | None] = mapped_column(Float)
    range_crit_upper: Mapped[float | None] = mapped_column(Float)
    range_crit_lower: Mapped[float | None] = mapped_column(Float)


class MeasurementType(Base):
    __tablename__ = "measurement_types"

    measurement_type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    measurement_type_name: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text, nullable=False)


class FailureType(Base):
    __tablename__ = "failure_types"

    failure_type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    failure_type_name: Mapped[str | None] = mapped_column(Text)
    is_preventive: Mapped[bool | None]
    failure_cause_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class SensorType(Base):
    __tablename__ = "sensor_types"

    type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type_name: Mapped[str] = mapped_column(Text, nullable=False)
    max_value: Mapped[float | None] = mapped_column(Float)
    min_value: Mapped[float | None] = mapped_column(Float)
    measurement_type_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_types.measurement_type_id"),
        nullable=False,
    )
    accuracy: Mapped[float | None] = mapped_column(Float)


class AssetFailureType(Base):
    __tablename__ = "asset_failure_types"

    asset_failure_type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    failure_type_id: Mapped[int] = mapped_column(
        ForeignKey("failure_types.failure_type_id"),
        nullable=False,
    )
    default_occurence_probability: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[int | None] = mapped_column(Integer)
    asset_failurecause_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Sensor(Base):
    __tablename__ = "sensors"

    sensor_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sensor_name: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_frequency: Mapped[float | None] = mapped_column(Float)
    ranges_id: Mapped[int | None] = mapped_column(ForeignKey("ranges.ranges_id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("sensor_types.type_id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)


class Measurement(Base):
    __tablename__ = "measurements"

    measurement_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.sensor_id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class EtaBeta(Base):
    __tablename__ = "etas_betas"

    eta_beta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    eta_value: Mapped[float] = mapped_column(Float, nullable=False)
    beta_value: Mapped[float] = mapped_column(Float, nullable=False)
    asset_failure_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_failure_types.asset_failure_type_id"),
        nullable=False,
    )
    learning_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AssetWorksheetList(Base):
    __tablename__ = "asset_worksheet_lists"

    asset_worksheet_list_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    maintenance_end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_sys_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    asset_failure_types_id: Mapped[int] = mapped_column(
        ForeignKey("asset_failure_types.asset_failure_type_id"),
        nullable=False,
    )
    failure_start_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    downtime_in_min: Mapped[int | None] = mapped_column(BigInteger)
    sys_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OperationsDoneList(Base):
    __tablename__ = "operations_done_lists"

    operations_done_lists_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    operation_done_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_template_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_worksheet_lists: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_worksheet_list_failure_start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_worksheet_lists", "asset_worksheet_list_failure_start_time"],
            [
                "asset_worksheet_lists.asset_worksheet_list_id",
                "asset_worksheet_lists.failure_start_time",
            ],
            name="fk_operations_done_lists_asset_worksheet_lists",
        ),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    asset_failure_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_failure_types.asset_failure_type_id"),
        nullable=False,
    )


class PredictionAssetLevel(Base):
    __tablename__ = "prediction_asset_levels"

    prediction_asset_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.prediction_id"), nullable=False)
    nowcast_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    nowcast_virtual_age: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_virtual_age: Mapped[float] = mapped_column(Float, nullable=False)
    nowcast_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    forecast_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)


class PredictionAssetFailureTypeLevel(Base):
    __tablename__ = "prediction_asset_failure_type_levels"

    prediction_asset_failure_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.prediction_id"), nullable=False)
    nowcast_failure_type_probability: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_failure_type_probability: Mapped[float] = mapped_column(Float, nullable=False)
    nowcast_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    forecast_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)


class SensorFailureType(Base):
    __tablename__ = "sensor_failure_types"

    sensor_failure_type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.sensor_id"), nullable=False)
    failure_type_id: Mapped[int] = mapped_column(ForeignKey("failure_types.failure_type_id"), nullable=False)


class SensorStatistic(Base):
    __tablename__ = "sensor_statistics"

    sensor_statistic_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.sensor_id"), nullable=False)
    standard_deviation_value: Mapped[float] = mapped_column(Float, nullable=False)
    average_value: Mapped[float] = mapped_column(Float, nullable=False)
    learning_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Gamma(Base):
    __tablename__ = "gammas"

    gamma_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    gamma_value: Mapped[float] = mapped_column(Float, nullable=False)
    sensor_failure_type_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_failure_types.sensor_failure_type_id"),
        nullable=False,
    )
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    learning_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PredictionJob(Base):
    __tablename__ = "prediction_jobs"

    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"),
        nullable=False,
    )
    endpoint_type: Mapped[str] = mapped_column(String, nullable=False)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.prediction_id"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
