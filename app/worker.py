import time, uuid, os, asyncio
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from loguru import logger
from pydantic import ValidationError

from .db import SyncSessionLocal
from .models import (
    PredictionJob, JobStatus,
    Asset, FailureType, AssetFailureType, EtaBeta,
    Prediction, MaintenanceList, OperationsMaintenanceList,
    AssetMaintenanceList, AssetFailureTypeAssetMaintenanceList
)
from .predict import predict_reliability, compute_prediction_future_time
from .utils import atomic_write_json
from .settings import settings
from .cmms import (cmms_get_asset,
                   cmms_get_maintenance_list,
                   cmms_get_failure_type,
                   cmms_post_asset_prediction_sync,
                   cmms_get_operation_maintenance_lists,
                   cmms_get_asset_maintenance_lists,
                   cmms_get_asset_failure_type_asset_maintenance_lists,
                   cmms_post_asset_failure_type_prediction_sync)
from .schemas import AssetPredictIn


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


def insert_prediction_row(session: Session, prediction_id: str | uuid.UUID, aft_id: str | uuid.UUID,
                          predicted_reliability: float,
                          pred_time: datetime, pred_future_time: datetime):
    # Normalize IDs (avoid uuid.UUID(UUID(...)) -> AttributeError)
    pred_uuid = prediction_id if isinstance(prediction_id, uuid.UUID) else uuid.UUID(str(prediction_id))
    aft_uuid = aft_id if isinstance(aft_id, uuid.UUID) else uuid.UUID(str(aft_id))
    pr = max(0.0, min(1.0, float(predicted_reliability)))

    session.add(Prediction(
        prediction_id=pred_uuid,
        asset_failure_type_id=aft_uuid,
        predicted_reliability=pr,
        time=pred_time,
        prediction_future_time=pred_future_time,
    ))
    session.flush()


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


def has_any_maintenance_list_for_asset(session: Session, asset_id: str) -> bool:
    """
    True if the asset has at least one asset_maintenance_list row.
    """
    a_id = uuid.UUID(asset_id)
    row = session.execute(
        select(AssetMaintenanceList.asset_maintenance_list_id)
        .where(AssetMaintenanceList.asset_id == a_id)
        .limit(1)
    ).first()
    return bool(row)


def has_gamma_data(session: Session, asset_id: str, failure_type_id: str | None,
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
        dict(asset_id=uuid.UUID(asset_id), ftid=uuid.UUID(failure_type_id),
             t_start=start, t_end=end)
    ).first()
    return bool(q)


def has_maintenanace_list(session: Session, operation_id: str) -> bool:
    """
    Van-e maintenance_list az adott operation_id-hez?
    operations_maintenance_list táblában keresünk.
    """
    op_id = uuid.UUID(operation_id)
    row = session.execute(
        select(OperationsMaintenanceList.maintenance_list_id)
        .where(OperationsMaintenanceList.operation_id == op_id)
        .limit(1)
    ).first()
    return bool(row)


def ensure_maintenance_list_row(session: Session, maintenance_list_id: str) -> bool:
    """
    Ensure a MaintenanceList row exists. If missing, try to fetch details from CMMS.
    """
    ml_uuid = uuid.UUID(maintenance_list_id)
    ml = session.get(MaintenanceList, ml_uuid)
    if ml:
        return True

    ml_json = None
    try:
        ml_json = asyncio.run(cmms_get_maintenance_list(maintenance_list_id))
    except Exception:
        pass

    session.add(MaintenanceList(
        maintenance_list_id=ml_uuid,
        maintenance_list_name=(ml_json or {}).get("maintenance_list_name", "")
    ))
    session.flush()
    return True


def ensure_operation_maintenanace_lists(session: Session, operation_id: str) -> list[str]:
    # 1) Try DB mapping first
    op_uuid = uuid.UUID(operation_id)
    db_ids = session.execute(
        select(OperationsMaintenanceList.maintenance_list_id)
        .where(OperationsMaintenanceList.operation_id == op_uuid)
    ).scalars().all()
    if db_ids:
        return [str(x) for x in db_ids]

    # 2) Fallback to CMMS
    rows = []
    try:
        rows = asyncio.run(cmms_get_operation_maintenance_lists(operation_id)) or []
    except Exception:
        rows = []

    ml_ids: list[str] = []
    for r in rows:
        ml_id = r.get("maintenance_list_id")
        if not ml_id:
            continue
        ml_ids.append(ml_id)
        # ensure maintenance_list row locally
        ensure_maintenance_list_row(session, ml_id)
        # ensure operation -> maintenance_list mapping
        session.merge(OperationsMaintenanceList(
            maintenance_list_id=uuid.UUID(ml_id),
            operation_id=op_uuid
        ))
    if ml_ids:
        session.flush()
    return bool(ml_ids)


def ensure_asset_maintenance_lists(session: Session, asset_id: str) -> list[str]:
    """
    Ensure maintenance_list mappings for the given asset.
    - If mappings exist locally, return them.
    - Else fetch from CMMS, upsert maintenance_list rows and asset_maintenance_list mappings.
    - If CMMS rows include operation_id, also upsert operations_maintenance_list.
    Returns the maintenance_list_ids mapped to the asset.
    """
    a_uuid = uuid.UUID(asset_id)

    # 1) Local mappings
    db_ml_ids = session.execute(
        select(AssetMaintenanceList.maintenance_list_id)
        .where(AssetMaintenanceList.asset_id == a_uuid)
    ).scalars().all()
    if db_ml_ids:
        return [str(x) for x in db_ml_ids]

    # 2) Fallback to CMMS
    rows: list[dict] = []
    try:
        rows = asyncio.run(cmms_get_asset_maintenance_lists(asset_id)) or []
    except Exception:
        rows = []

    if not rows:
        return []

    for r in rows:
        ml_id = r.get("maintenance_list_id")
        if not ml_id:
            continue
        ml_uuid = uuid.UUID(ml_id)

        # Ensure maintenance_list row exists (pulls name if needed)
        ensure_maintenance_list_row(session, ml_id)

        # Ensure asset -> maintenance_list mapping
        exists_aml = session.execute(
            select(AssetMaintenanceList.asset_maintenance_list_id).where(
                AssetMaintenanceList.asset_id == a_uuid,
                AssetMaintenanceList.maintenance_list_id == ml_uuid
            ).limit(1)
        ).first()
        if not exists_aml:
            session.add(AssetMaintenanceList(asset_id=a_uuid, maintenance_list_id=ml_uuid))

        # Optionally ensure operation -> maintenance_list mapping if provided by CMMS
        op_id = r.get("operation_id")
        if op_id:
            op_uuid = uuid.UUID(op_id)
            exists_oml = session.execute(
                select(OperationsMaintenanceList.maintenance_list_id).where(
                    OperationsMaintenanceList.maintenance_list_id == ml_uuid,
                    OperationsMaintenanceList.operation_id == op_uuid
                ).limit(1)
            ).first()
            if not exists_oml:
                session.add(OperationsMaintenanceList(
                    maintenance_list_id=ml_uuid,
                    operation_id=op_uuid
                ))

    session.flush()

    # Re-read and return
    db_ml_ids = session.execute(
        select(AssetMaintenanceList.maintenance_list_id)
        .where(AssetMaintenanceList.asset_id == a_uuid)
    ).scalars().all()
    return [str(x) for x in db_ml_ids]


def get_latest_eta_beta(session: Session, asset_failure_type_id: str, asof: datetime):
    """
    Legutóbbi eta/beta az adott asset_failure_type-re, as-of 'asof' időpontra.
    """
    row = session.execute(
        select(EtaBeta.eta_value, EtaBeta.beta_value)
        .where(EtaBeta.asset_failure_type_id == uuid.UUID(asset_failure_type_id),
               EtaBeta.time <= asof)
        .order_by(EtaBeta.time.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else (None, None)


def ensure_asset_failure_type_id(session: Session, asset_id: str,
                                 failure_type_id: str | None) -> str | None:
    """
    Keresünk AssetFailureType rekordot. Ha nincs failure_type_id: None.
    """
    if failure_type_id is None:
        return None
    aft = session.execute(
        select(AssetFailureType.asset_failure_type_id).where(
            AssetFailureType.asset_id == uuid.UUID(asset_id),
            AssetFailureType.failure_type_id == uuid.UUID(failure_type_id)
        ).limit(1)
    ).scalar_one_or_none()
    return str(aft) if aft else None


def ensure_asset_maintenance_lists_asset_failure_type(
    session: Session,
    asset_id: str,
    failure_type_id: str,
) -> list[str]:
    """
    Ensure AFT ↔ AML mappings for the given asset and failure type.
    - Ensures AMLs for asset (DB or CMMS)
    - Ensures AssetFailureType exists
    - Creates missing AssetFailureTypeAssetMaintenanceList mappings
    Returns maintenance_list_ids mapped for this AFT.
    """
    a_uuid = uuid.UUID(asset_id)

    # Ensure AMLs exist for the asset
    ml_ids = ensure_asset_maintenance_lists(session, asset_id)
    if not ml_ids:
        return []

    # Resolve AFT id (scalar UUID string)
    aft_id = ensure_asset_failure_type_id(session, asset_id, failure_type_id)
    if not aft_id:
        return []
    aft_uuid = uuid.UUID(aft_id)

    # Get all AML rows for this asset (need AML ids and their ML ids)
    aml_rows = session.execute(
        select(
            AssetMaintenanceList.asset_maintenance_list_id,
            AssetMaintenanceList.maintenance_list_id,
        ).where(AssetMaintenanceList.asset_id == a_uuid)
    ).all()

    # Existing mappings for this AFT
    existing_aml_ids: set[uuid.UUID] = set(session.execute(
        select(AssetFailureTypeAssetMaintenanceList.asset_maintenance_list_id)
        .where(AssetFailureTypeAssetMaintenanceList.asset_failure_type_id == aft_uuid)
    ).scalars().all())

    # Create missing mappings  # ! CMMS-bol lekerni, ha nincs sajat db-ben
    for aml_id, _ml_id in aml_rows:
        if aml_id in existing_aml_ids:
            continue
        session.add(AssetFailureTypeAssetMaintenanceList(
            asset_failure_type_id=aft_uuid,
            asset_maintenance_list_id=aml_id,
            default_reliability=1
        ))

    session.flush()

    # Return the maintenance_list_ids mapped for this AFT (from the asset’s AMLs)
    return [str(ml_id) for (_aml_id, ml_id) in aml_rows]


def process_job(session: Session, job: PredictionJob):
    try:
        # Validate the payload
        p = AssetPredictIn(**job.payload)
    except ValidationError as e:
        job.status = JobStatus.error
        job.error_message = f"Payload validation failed: {e}"
        session.commit()
        return

    asset_id = str(p.asset_id)
    start = p.failure_start_time
    end = p.maintenance_end_time
    source_time = p.source_sys_time
    failure_type_id = str(p.failure_type_id)
    op_raw = p.operation_id
    operation_ids: list[str] = [str(x) for x in (op_raw if isinstance(op_raw, (list, tuple)) else [op_raw])]

    # 1) Ensure data exists
    if not ensure_asset(session, asset_id):
        job.status = JobStatus.not_found
        job.error_message = "Asset not found in DB/CMMS"
        session.commit()
        return

    if job.endpoint_type == "asset_failure_type_predict":
        if not ensure_failure_type(session, failure_type_id):
            job.status = JobStatus.not_found
            job.error_message = "Failure type not found in DB/CMMS"
            session.commit()
            return

    # 2) Check for data
    # if not has_gamma_data(session, asset_id, failure_type_id, start, end):
    #    job.status = JobStatus.not_found
    #    job.error_message = "No gamma data in time window for asset/failure_type"
    #    session.commit()
    #    return

    any_oml = False
    for op_id in operation_ids:
        if has_maintenanace_list(session, op_id) or ensure_operation_maintenanace_lists(session, op_id):
            any_oml = True
    if not any_oml:
        job.status = JobStatus.not_found
        job.error_message = "No maintenance_list data for any operation_id"
        session.commit()
        return

    # 3) asset_failure_type_id feloldás
    if job.endpoint_type == "asset_failure_type_predict":
        aft_id = ensure_asset_failure_type_id(session, asset_id, failure_type_id)
        if aft_id is None:
            job.status = JobStatus.not_found
            job.error_message = "asset_failure_type mapping not found"
            session.commit()
            return

    aml = ensure_asset_maintenance_lists(session, asset_id)
    if aml is None:
        job.status = JobStatus.not_found
        job.error_message = "No asset_maintenance_list mapping found for asset"
        session.commit()
        return

    if job.endpoint_type == "asset_failure_type_predict":
        amlaft = ensure_asset_maintenance_lists_asset_failure_type(session, asset_id, failure_type_id)
        if not amlaft:
            job.status = JobStatus.not_found
            job.error_message = "asset_maintenanace_list_asset_failure_type mapping not found"
            session.commit()
            return

    # 4) Eta/Beta felkutatása (legutóbbi érték a window végéig)
    # eta_val, beta_val = get_latest_eta_beta(session, aft_id, end)

    # 5) Predikciós horizont (pl. +7 nap)
    prediction_future_time = compute_prediction_future_time(end, days_ahead=7)

    if job.endpoint_type == "asset_predict":
        # 6) Predikció
        value = predict_reliability(
            prediction_future_time=prediction_future_time,
            failure_start_time=start,
            maintenance_end_time=end,
            source_sys_time=source_time,
            # eta_value=eta_val,
            # beta_value=beta_val,
            # default_reliability=p.get("default_reliability"),
        )
        print(value)
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
            resp = cmms_post_asset_prediction_sync(out)
            logger.info("CMMS asset_prediction response: {}", resp)  # pass resp as arg
            if isinstance(resp, dict) and resp.get("error"):
                raise RuntimeError(resp["error"])
        except Exception as e:
            job.status = JobStatus.error
            job.error_message = f"CMMS POST failed: {e}"
            job.prediction_id = pred_id
            session.commit()
            return
    elif job.endpoint_type == "asset_failure_type_predict":
        # 6) Predikció
        value = predict_reliability(
            prediction_future_time=prediction_future_time,
            failure_start_time=start,
            maintenance_end_time=end,
            source_sys_time=source_time,
            # eta_value=eta_val,
            # beta_value=beta_val,
            # default_reliability=p.get("default_reliability"),
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
            resp = cmms_post_asset_failure_type_prediction_sync(out)
            logger.info(f"CMMS asset_prediction response: {resp}")  # was: "{resp}"
            if isinstance(resp, dict) and resp.get("error"):
                raise RuntimeError(resp["error"])
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


def main():
    logger.info("DB-queue worker started (no Redis).")
    while True:
        try:
            with session_scope() as session:
                job = claim_one_job(session)
                if not job:
                    time.sleep(POLL_INTERVAL_SEC)
                    continue
                process_job(session, job)
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
