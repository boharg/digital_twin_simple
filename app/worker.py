import time, uuid, os, asyncio
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from loguru import logger
from pydantic import ValidationError

from .db import SyncSessionLocal
from .models import (
    PredictionJob, JobStatus,
    Asset, FailureType, AssetFailureType,
    Sensor, SensorFailureType, Gamma, EtaBeta,
    Prediction, MaintenanceList, OperationsMaintenanceList,
    AssetMaintenanceList, AssetFailureTypeAssetMaintenanceList
)
from .predict import predict_reliability, compute_prediction_future_time
from .utils import atomic_write_json
from .settings import settings
from .cmms import (cmms_get_asset, cmms_get_failure_type,
                   cmms_post_asset_prediction_sync,
                   cmms_post_asset_failure_type_prediction_sync,
                   cmms_get_operations_for_maintenance_list)
from .schemas import AssetPredictIn, AssetFailureTypePredictIn


POLL_INTERVAL_SEC = 1.0


@contextmanager
def session_scope():
    session: Session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def claim_one_job(session: Session) -> PredictionJob | None:
    row = session.execute(
        text("""
        SELECT job_id
        FROM prediction_jobs
        WHERE status = 'queued'
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """)
    ).first()
    if not row:
        return None
    job = session.get(PredictionJob, row[0])
    job.status = JobStatus.processing
    session.commit()
    session.refresh(job)
    return job


def ensure_asset(session: Session, asset_id: str) -> bool:
    asset = session.get(Asset, asset_id)
    if asset:
        return True
    # Ha nincs, megpróbáljuk CMMS-ből betölteni
    asset_json = asyncio.run(cmms_get_asset(asset_id))
    if not asset_json:
        return False
    session.merge(Asset(asset_id=asset_json["asset_id"],
                        asset_name=asset_json.get("asset_name", "")))
    session.commit()
    return True


def ensure_failure_type(session: Session, failure_type_id: str | None) -> bool:
    if failure_type_id is None:
        return False
    ft = session.get(FailureType, failure_type_id)
    if ft:
        return True
    ft_json = asyncio.run(cmms_get_failure_type(failure_type_id))
    if not ft_json:
        return False
    session.merge(FailureType(
        failure_type_id=ft_json["failure_type_id"],
        failure_type_name=ft_json.get("failure_type_name", "")
    ))
    session.commit()
    return True


def resolve_asset_failure_type_id(session: Session, asset_id: str,
                                 failure_type_id: str | None) -> str | None:
    """
    Keresünk AssetFailureType rekordot. Ha nincs failure_type_id: None.
    """
    if failure_type_id is None:
        return None
    aft = session.execute(
        select(AssetFailureType.asset_failure_type_id).where(
            AssetFailureType.asset_id == asset_id,
            AssetFailureType.failure_type_id == failure_type_id
        ).limit(1)
    ).scalar_one_or_none()
    return aft


def has_gamma_data(session: Session, asset_id: str, failure_type_id: int | None,
                   start: datetime, end: datetime) -> bool:
    """
    Van-e gamma adat a megadott asset + failure_type kapcsolathoz az időablakban?
    gamma -> sensor_failure_type -> sensor (asset_id) + failure_type_id
    """
    if failure_type_id is None:
        return False
    q = session.execute(
        text("""
        SELECT 1
        FROM gamma g
        JOIN sensor_failure_type sft ON sft.sensor_failure_type_id = g.sensor_failure_type_id
        JOIN sensor s ON s.sensor_id = sft.sensor_id
        WHERE s.asset_id = :asset_id
          AND sft.failure_type_id = :ftid
          AND g.time BETWEEN :t_start AND :t_end
        LIMIT 1
        """),
        dict(asset_id=asset_id, ftid=failure_type_id, t_start=start, t_end=end)
    ).first()
    return bool(q)


def get_latest_eta_beta(session: Session, asset_failure_type_id: str, asof: datetime):
    """
    Legutóbbi eta/beta az adott asset_failure_type-re, as-of 'asof' időpontra.
    """
    row = session.execute(
        select(EtaBeta.eta_value, EtaBeta.beta_value)
        .where(EtaBeta.asset_failure_type_id == asset_failure_type_id,
               EtaBeta.time <= asof)
        .order_by(EtaBeta.time.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else (None, None)


def insert_prediction_row(session: Session, prediction_id: uuid.UUID, aft_id: int,
                          predicted_reliability: float,
                          pred_time: datetime, pred_future_time: datetime):
    session.add(Prediction(
        prediction_id=prediction_id,
        asset_failure_type_id=aft_id,
        predicted_reliability=predicted_reliability,
        time=pred_time,
        prediction_future_time=pred_future_time
    ))
    session.commit()


def sync_operations_for_maintenance_list(session: Session, maintenance_list_id: str):
    ops = asyncio.run(cmms_get_operations_for_maintenance_list(maintenance_list_id))
    for o in ops:
        key = {
            "maintenance_list_id": uuid.UUID(maintenance_list_id),
            "operation_id": uuid.UUID(o["operation_id"])
        }
        existing = session.get(OperationsMaintenanceList, key)
        if not existing:
            session.add(OperationsMaintenanceList(**key))
    session.commit()


def sync_asset_maintenance_list(
    session: Session,
    asset_id: str,
    maintenance_list_id: str,
    maintenance_list_name: str | None = None,
    is_preventive: bool | None = None
):
    asset_id = uuid.UUID(asset_id)
    maintenance_list_id = uuid.UUID(maintenance_list_id)

    exists = session.execute(
        select(AssetMaintenanceList.asset_maintenance_list_id).where(
            AssetMaintenanceList.asset_id == asset_id,
            AssetMaintenanceList.maintenance_list_id == maintenance_list_id
        ).limit(1)
    ).first()
    if not exists:
        session.add(AssetMaintenanceList(asset_id=asset_id,
                                         maintenance_list_id=maintenance_list_id))
    session.flush()


def sync_asset_failure_type_asset_maintenance_list(
    session: Session,
    asset_id: str,
    failure_type_id: str,
    maintenance_list_id: str,
    default_reliability: float | None = None
):
    """
    Ensure AssetFailureType, AssetMaintenanceList (already), then AFT ↔ AML mapping.
    """
    asset_id = uuid.UUID(asset_id)
    failure_type_id = uuid.UUID(failure_type_id)
    maintenance_list_id = uuid.UUID(maintenance_list_id)

    # Ensure FailureType
    ensure_failure_type(session, int(failure_type_id))

    # Ensure AssetFailureType
    aft = resolve_asset_failure_type_id(session, str(asset_id), int(failure_type_id))

    # Find existing AssetMaintenanceList row
    aml = sync_asset_maintenance_list(
        session,
        asset_id=str(asset_id),
        maintenance_list_id=str(maintenance_list_id)
    )

    # Ensure AFT ↔ AML mapping
    exists = session.execute(
        select(AssetFailureTypeAssetMaintenanceList.asset_failure_type_asset_maintenance_list_id).where(
            AssetFailureTypeAssetMaintenanceList.asset_failure_type_id == aft.asset_failure_type_id,
            AssetFailureTypeAssetMaintenanceList.asset_maintenance_list_id == aml.asset_maintenance_list_id
        ).limit(1)
    ).first()
    if not exists:
        session.add(AssetFailureTypeAssetMaintenanceList(
            asset_failure_type_id=aft.asset_failure_type_id,
            asset_maintenance_list_id=aml.asset_maintenance_list_id,
            default_reliability=default_reliability
        ))

    session.flush()


def process_job(session: Session, job: PredictionJob):
    try:
        # Validate the payload
        p = AssetPredictIn(**job.payload)
    except ValidationError as e:
        job.status = JobStatus.error
        job.error_message = f"Payload validation failed: {e}"
        session.commit()
        return

    asset_id = p.asset_id
    start = p.failure_start_time
    end = p.maintenance_end_time
    source_time = p.source_sys_time
    failure_type_id = p.failure_type_id

    # 1) Ensure asset exists
    if not ensure_asset(session, asset_id):
        job.status = JobStatus.not_found
        job.error_message = "Asset not found in DB/CMMS"
        session.commit()
        return

    # 2) Check for gamma data
    if not has_gamma_data(session, asset_id, failure_type_id, start, end):
        job.status = JobStatus.not_found
        job.error_message = "No gamma data in time window for asset/failure_type"
        session.commit()
        return

    # 3) asset_failure_type_id feloldás
    aft_id = resolve_asset_failure_type_id(session, asset_id, failure_type_id)
    if aft_id is None:
        job.status = JobStatus.not_found
        job.error_message = "asset_failure_type mapping not found"
        session.commit()
        return

    # 4) Eta/Beta felkutatása (legutóbbi érték a window végéig)
    eta_val, beta_val = get_latest_eta_beta(session, aft_id, end)

    # 5) Predikciós horizont (pl. +7 nap)
    prediction_future_time = compute_prediction_future_time(end, days_ahead=7)

    # 6) Predikció
    value = predict_reliability(
        prediction_future_time=prediction_future_time,
        failure_start_time=start,
        maintenance_end_time=end,
        source_sys_time=source_time,
        eta_value=eta_val,
        beta_value=beta_val,
        default_reliability=p.get("default_reliability"),
    )

    # 7) prediction_id + JSON + CMMS POST + prediction tábla insert
    pred_id = uuid.uuid4()
    out = {"prediction_id": str(pred_id), "predicted_reliability": float(value)}

    # JSON
    json_path = os.path.join(settings.DATA_DIR, f"{pred_id}.json")
    atomic_write_json(json_path, out)

    # prediction tábla
    insert_prediction_row(
        session=session,
        prediction_id=pred_id,
        aft_id=aft_id,
        predicted_reliability=float(value),
        pred_time=source_time,
        pred_future_time=prediction_future_time
    )

    # CMMS POST (ha elbukik, itt nem retry-olunk automatikusan – log + status=error)
    try:
        cmms_post_asset_prediction_sync(out)
    except Exception as e:
        job.status = JobStatus.error
        job.error_message = f"CMMS POST failed: {e}"
        job.prediction_id = pred_id
        session.commit()
        return

    # 8) kész
    job.status = JobStatus.done
    job.prediction_id = pred_id
    session.commit()


def process_asset_failure_type_job(session: Session, job: PredictionJob):
    try:
        # Validate the payload
        p = AssetFailureTypePredictIn(**job.payload)
    except ValidationError as e:
        job.status = JobStatus.error
        job.error_message = f"Payload validation failed: {e}"
        session.commit()
        return

    asset_id = p.asset_id
    start = p.failure_start_time
    end = p.maintenance_end_time
    source_time = p.source_sys_time
    failure_type_id = p.failure_type_id

    # 1) Ensure asset exists
    if not ensure_asset(session, asset_id):
        job.status = JobStatus.not_found
        job.error_message = "Asset not found in DB/CMMS"
        session.commit()
        return

    # 2) Check for gamma data
    if not has_gamma_data(session, asset_id, failure_type_id, start, end):
        job.status = JobStatus.not_found
        job.error_message = "No gamma data in time window for asset/failure_type"
        session.commit()
        return

    # 3) Resolve asset_failure_type_id
    aft_id = resolve_asset_failure_type_id(session, asset_id, failure_type_id)
    if aft_id is None:
        job.status = JobStatus.not_found
        job.error_message = "asset_failure_type mapping not found"
        session.commit()
        return

    # 4) Retrieve Eta/Beta values (latest values up to the window end)
    eta_val, beta_val = get_latest_eta_beta(session, aft_id, end)

    # 5) Compute prediction horizon (e.g., +7 days)
    prediction_future_time = compute_prediction_future_time(end, days_ahead=7)

    # 6) Perform prediction
    value = predict_reliability(
        prediction_future_time=prediction_future_time,
        failure_start_time=start,
        maintenance_end_time=end,
        source_sys_time=source_time,
        eta_value=eta_val,
        beta_value=beta_val,
        default_reliability=p.default_reliability,
    )

    # 7) Generate prediction_id, save JSON, insert into prediction table, and post to CMMS
    pred_id = uuid.uuid4()
    out = {"prediction_id": str(pred_id), "predicted_reliability": float(value)}

    # Save JSON
    json_path = os.path.join(settings.DATA_DIR, f"{pred_id}.json")
    atomic_write_json(json_path, out)

    # Insert into prediction table
    insert_prediction_row(
        session=session,
        prediction_id=pred_id,
        aft_id=aft_id,
        predicted_reliability=float(value),
        pred_time=source_time,
        pred_future_time=prediction_future_time
    )

    # Post to CMMS
    try:
        cmms_post_asset_failure_type_prediction_sync(out)
    except Exception as e:
        job.status = JobStatus.error
        job.error_message = f"CMMS POST failed: {e}"
        job.prediction_id = pred_id
        session.commit()
        return

    # 8) Mark job as done
    job.status = JobStatus.done
    job.prediction_id = pred_id
    session.commit()


def main():
    logger.info("DB-queue worker started (no Redis).")
    while True:
        try:
            with session_scope() as session:
                job = claim_one_job(session)
                if not job:
                    time.sleep(POLL_INTERVAL_SEC)
                    continue
                logger.info(f"Processing job_id={job.job_id}")
                if job.job_type == "asset_predict":
                    process_job(session, job)
                elif job.job_type == "asset_failure_type_predict":
                    process_asset_failure_type_job(session, job)
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
