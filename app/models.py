from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (String, JSON, Enum, Index, Float, Text, 
                        Integer, ForeignKey, DateTime, BigInteger, Boolean)
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum
import uuid


class Base(DeclarativeBase):
    pass


# ---- ÚJ DB-queue tábla ---------------------------------------------
class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    not_found = "not_found"
    error = "error"


class PredictionJob(Base):
    """
    Tartós job tábla: request payload + státusz + hiba.
    Ezt a táblát a worker 'claimeli' SKIP LOCKED-ral.
    """
    __tablename__ = "prediction_jobs"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String, nullable=True)  # pl. "asset_predict" vagy "asset_failure_type_predict"
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Index("ux_prediction_jobs_request_hash", PredictionJob.request_hash, unique=True)


# ---- LÉTEZŐ táblákhoz minimális ORM mappingek (nem hozunk létre sémát) -----
class Asset(Base):
    __tablename__ = "asset"
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)


class FailureType(Base):
    __tablename__ = "failure_type"
    failure_type_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    failure_type_name: Mapped[str] = mapped_column(String, nullable=False)
    is_preventive: Mapped[bool] = mapped_column()


class Failure(Base):
    __tablename__ = "failure"
    failure_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    failure_name: Mapped[str] = mapped_column(String, nullable=False)
    is_preventive: Mapped[bool] = mapped_column()


class AssetFailureType(Base):
    __tablename__ = "asset_failure_type"
    asset_failure_type_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset.asset_id"), nullable=False)
    failure_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("failure_type.failure_type_id"), nullable=False)
    criticality: Mapped[float | None] = mapped_column(Float)


class Sensor(Base):
    __tablename__ = "sensor"
    sensor_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    sensor_name: Mapped[str] = mapped_column(String, nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset.asset_id"), nullable=False)
    measurement_frequency: Mapped[float | None] = mapped_column(Float)


class SensorFailureType(Base):
    __tablename__ = "sensor_failure_type"
    sensor_failure_type_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensor.sensor_id"), nullable=False)
    failure_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("failure_type.failure_type_id"), nullable=False)


class Gamma(Base):
    __tablename__ = "gamma"
    gamma_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gamma_value: Mapped[float] = mapped_column(Float, nullable=False)
    sensor_failure_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sensor_failure_type.sensor_failure_type_id"), nullable=False)
    contribution: Mapped[float | None] = mapped_column(Float)


class EtaBeta(Base):
    __tablename__ = "eta_beta"
    eta_beta_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    eta_value: Mapped[float] = mapped_column(Float, nullable=False)
    beta_value: Mapped[float] = mapped_column(Float, nullable=False)
    asset_failure_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset_failure_type.asset_failure_type_id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Prediction(Base):
    __tablename__ = "prediction"
    prediction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    asset_failure_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset_failure_type.asset_failure_type_id"), nullable=False)
    predicted_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # mikor készült a predikció (pl. source_sys_time)
    prediction_future_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # amire jósolunk


class MaintenanceList(Base):
    __tablename__ = "maintenance_list"
    maintenance_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    maintenance_list_name: Mapped[str] = mapped_column(String, nullable=False)
    is_preventive: Mapped[bool | None] = mapped_column(Boolean)


class OperationsMaintenanceList(Base):
    __tablename__ = "operations_maintenance_list"
    maintenance_list_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_list.maintenance_list_id"),
        primary_key=True
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True
    )


class AssetMaintenanceList(Base):
    __tablename__ = "asset_maintenance_list"
    asset_maintenance_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset.asset_id"), nullable=False)
    maintenance_list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maintenance_list.maintenance_list_id"), nullable=False)


class AssetFailureTypeAssetMaintenanceList(Base):
    __tablename__ = "asset_failure_type_asset_maintenance_list"
    asset_failure_type_asset_maintenance_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    asset_failure_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset_failure_type.asset_failure_type_id"), nullable=False)
    asset_maintenance_list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset_maintenance_list.asset_maintenance_list_id"), nullable=False)
    default_reliability: Mapped[float | None] = mapped_column(Float)
