import time
import os
import asyncio
from datetime import datetime
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from loguru import logger
from pydantic import ValidationError

from .job_queue import session_scope, requeue_stuck_jobs, claim_one_job, _is_admin_shutdown_error

from ..models import (PredictionJob, JobStatus, AssetFailureType, Prediction)
from .predict import predict, compute_prediction_future_time
from ..utils import atomic_write_json
from .settings import settings
from .cmms import (cmms_post_asset_prediction_sync,
                   cmms_post_asset_failure_cause_prediction)

from ..schemas import AssetPredictIn, AssetFailureTypePredictIn
from ..data_sync import ensure_asset, ensure_failure_type, ensure_asset_failure_types


POLL_INTERVAL_SEC = 1.0
ALLOWED_OPERATION_TYPES = {"BOTH", "CORRECTIVE", "PREVENTIVE"}


def insert_prediction_row(
    session: Session,
    asset_id: int,
    aft_id: int,
    prediction_id: int | None = None,
) -> int:
    if prediction_id is not None:
        pred = session.get(Prediction, int(prediction_id))
        if pred:
            pred.asset_id = asset_id
            pred.asset_failure_type_id = aft_id
            session.flush()
            return int(pred.prediction_id)

    pred = Prediction(asset_id=asset_id, asset_failure_type_id=aft_id)
    if prediction_id is not None:
        pred.prediction_id = prediction_id

    session.add(pred)
    session.flush()
    return pred.prediction_id


def process_job(session: Session, job: PredictionJob):
    if job.endpoint_type == "workrequest":
        job.status = JobStatus.not_found
        job.error_message = "workrequest endpoint is not implemented yet"
        session.commit()
        return

    try:
        if job.endpoint_type == "asset_failure_type_predict":
            p = AssetFailureTypePredictIn(**job.payload)
        else:
            p = AssetPredictIn(**job.payload)
    except ValidationError as e:
        job.status = JobStatus.error
        job.error_message = f"Payload validation failed: {e}"
        session.commit()
        return

    asset_id = int(p.asset_id)

    # Ensure asset exists before any dependent inserts to avoid FK violations
    if not ensure_asset(session, asset_id):
        job.status = JobStatus.not_found
        job.error_message = "Asset not found in DB/CMMS"
        session.commit()
        return

    # ---- failure_type_ids normalizálás ----
    ft_raw = getattr(p, "failure_type_ids", None)
    if ft_raw is None:
        failure_type_ids: list[int] = []
    elif isinstance(ft_raw, (list, tuple)):
        failure_type_ids = [int(x) for x in ft_raw]
    else:
        failure_type_ids = [int(ft_raw)]

    asset_failure_type_ids: list[int] = []
    if job.endpoint_type == "asset_failure_type_predict":
        if len(failure_type_ids) == 0:
            job.status = JobStatus.error
            job.error_message = "failure_type_ids is required and cannot be empty for asset_failure_type_predict"
            session.commit()
            return

        synced_aft_ids = ensure_asset_failure_types(session, asset_id)
        if not synced_aft_ids:
            job.status = JobStatus.not_found
            job.error_message = "No asset_failure_types data in DB/CMMS"
            session.commit()
            return

        aft_map_by_failure_type: dict[int, int] = dict(
            session.execute(
                select(AssetFailureType.failure_type_id, AssetFailureType.asset_failure_type_id)
                .where(AssetFailureType.asset_id == asset_id)
            ).all()
        )

        for ftid in failure_type_ids:
            if int(ftid) not in aft_map_by_failure_type:
                job.status = JobStatus.not_found
                job.error_message = f"asset_failure_type_id not found for failure_type_id: {ftid}"
                session.commit()
                return
            aft_id = aft_map_by_failure_type[int(ftid)]
            asset_failure_type_ids.append(int(aft_id))
            if not ensure_failure_type(session, ftid):
                job.status = JobStatus.error
                job.error_message = f"Failure type not found in DB/CMMS: {ftid}"
                session.commit()
                return

    # Minden failure_type_id ellenőrzése (DB -> CMMS). Ha nincs, hiba.
    for ftid in failure_type_ids:
        if not ensure_failure_type(session, ftid):
            job.status = JobStatus.error
            job.error_message = f"Failure type not found in DB/CMMS: {ftid}"
            session.commit()
            return

    start = p.failure_start_time
    end = p.maintenance_end_time
    source_time = p.source_sys_time

    op_raw = p.operation_ids
    operation_ids: list[int] = [x for x in (op_raw if isinstance(op_raw, (list, tuple)) else [op_raw])]

    aft_id: int | None = None
    if job.endpoint_type == "asset_failure_type_predict":
        aft_id = int(asset_failure_type_ids[0])
    else:
        asset_failure_type_ids = ensure_asset_failure_types(session, asset_id)
        if not asset_failure_type_ids:
            job.status = JobStatus.not_found
            job.error_message = "No asset_failure_types data in DB/CMMS"
            session.commit()
            return
        aft_id = int(asset_failure_type_ids[0])

    prediction_future_time = compute_prediction_future_time(end, days_ahead=7)

    if job.endpoint_type == "asset_predict":
        prediction = predict(
            asset_id=asset_id,
            prediction_future_time=prediction_future_time,
            failure_start_time=start,
            maintenance_end_time=end,
            source_sys_time=source_time,
            operation_ids=operation_ids,
        )
        print(prediction)
        pr = max(0.0, min(0.99, float(prediction["predicted_reliability"])))
        pred_id = insert_prediction_row(
            session=session,
            asset_id=asset_id,
            aft_id=aft_id,
            prediction_id=job.prediction_id,
        )
        out = {"prediction_id": pred_id, "asset_id": asset_id, "predicted_reliability": pr}

        # JSON
        json_path = os.path.join(settings.DATA_DIR, f"{pred_id}.json")
        atomic_write_json(json_path, out)

        # CMMS POST (ha elbukik, itt nem retry-olunk automatikusan – log + status=error)
        try:
            resp = asyncio.run(cmms_post_asset_prediction_sync(out))
            logger.info("CMMS asset_prediction response: {}", resp)
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
        prediction = predict(
            asset_id=asset_id,
            prediction_future_time=prediction_future_time,
            failure_start_time=start,
            maintenance_end_time=end,
            source_sys_time=source_time,
            operation_ids=operation_ids,
            failure_type_ids=failure_type_ids
        )

        # 7) prediction_id + JSON + CMMS POST + prediction tábla insert
        pr = max(0.0, min(0.99, float(prediction["predicted_reliability"])))
        pred_id = insert_prediction_row(
            session=session,
            asset_id=asset_id,
            aft_id=aft_id,
            prediction_id=job.prediction_id,
        )
        out = {
            "prediction_id": pred_id,
            "asset_failure_type_ids": asset_failure_type_ids,
            "failure_type_probability": prediction["failure_type_probability"],
        }

        # JSON
        json_path = os.path.join(settings.DATA_DIR, f"{pred_id}.json")
        atomic_write_json(json_path, out)

        try:
            resp = asyncio.run(cmms_post_asset_failure_cause_prediction(out))
            logger.info("CMMS asset_prediction response: {}", resp)
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
    last_requeue = 0.0
    while True:
        try:
            now = time.monotonic()
            if now - last_requeue >= 30.0:
                with session_scope() as session:
                    requeue_stuck_jobs(session)
                last_requeue = now

            # 1) Claim in a short-lived session/transaction
            with session_scope() as session:
                job = claim_one_job(session)
                job_id = job.job_id if job else None

            if not job_id:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            # 2) Process in a separate session so DB txn isn't held during CMMS calls
            with session_scope() as session:
                job = session.get(PredictionJob, job_id)
                if not job:
                    continue
                try:
                    process_job(session, job)
                except Exception as e:
                    logger.exception("Process job error: {}", e)
                    # Mark job for retry or failure in a fresh session to avoid broken txn
                    with session_scope() as session2:
                        job2 = session2.get(PredictionJob, job_id)
                        if job2:
                            if _is_admin_shutdown_error(e):
                                job2.status = JobStatus.queued
                                job2.error_message = "Retry: DB connection terminated"
                            else:
                                job2.status = JobStatus.error
                                job2.error_message = f"Unhandled error: {e}"
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
