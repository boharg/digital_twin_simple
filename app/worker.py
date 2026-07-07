import time
import os
import asyncio
from datetime import datetime
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from loguru import logger
from pydantic import ValidationError

from job_queue import (session_scope, requeue_stuck_jobs,
                       claim_one_job, _is_admin_shutdown_error, RETRY_LIMIT)

from .models import (PredictionJob, JobStatus, AssetFailureType, Prediction)
from .predict import predict, compute_prediction_future_time
from .utils import atomic_write_json
from .settings import settings
from .cmms import (cmms_post_asset_prediction_sync,
                   cmms_get_asset_failure_types,
                   cmms_post_asset_failure_type_prediction_sync)

from .schemas import AssetPredictIn, AssetFailureTypePredictIn
from data_sync import (_commit_before_cmms,
                       ensure_asset,
                       ensure_failure_type)


POLL_INTERVAL_SEC = 1.0
ALLOWED_OPERATION_TYPES = {"BOTH", "CORRECTIVE", "PREVENTIVE"}


def insert_prediction_row(session: Session, predicted_reliability: float, pred_time: datetime,
                          pred_future_time: datetime, aft_id: int | None = None, prediction_id: int | None = None) -> int:

    # CMMS expects predicted_reliability <= 0.99
    pr = max(0.0, min(0.99, float(predicted_reliability)))

    pred = Prediction(
        predicted_reliability=pr,
        time=pred_time,
        prediction_future_time=pred_future_time,
    )

    if aft_id is not None:
        pred.asset_failure_type_id = aft_id
    if prediction_id is not None:
        pred.prediction_id = prediction_id

    session.add(pred)
    session.flush()  # itt töltődik fel az autoincrement ID
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

        rows = []
        try:
            _commit_before_cmms(session)
            rows = asyncio.run(cmms_get_asset_failure_types(asset_id)) or []
        except Exception:
            rows = []

        if not rows:
            job.status = JobStatus.not_found
            job.error_message = "No asset_failure_types data in CMMS"
            session.commit()
            return

        # Map (asset_id, failure_type_id) -> (asset_failure_type_id, criticality)
        aft_map_by_key: dict[tuple[int, int], tuple[int, float | None]] = {}
        for r in rows:
            r_asset = r.get("asset_id")
            if r_asset is None or int(r_asset) != int(asset_id):
                continue
            # Ensure asset exists locally to avoid FK violations on asset_failure_type insert
            if not ensure_asset(session, int(r_asset)):
                job.status = JobStatus.not_found
                job.error_message = f"Asset not found in DB/CMMS: {r_asset}"
                session.commit()
                return
            aft_id = r.get("asset_failure_type_id")
            ft_id = r.get("failure_type_id")
            if aft_id is None or ft_id is None:
                continue
            aft_map_by_key[(int(asset_id), int(ft_id))] = (int(aft_id), r.get("criticality"))

        for ftid in failure_type_ids:
            key = (int(asset_id), int(ftid))
            if key not in aft_map_by_key:
                job.status = JobStatus.not_found
                job.error_message = f"asset_failure_type_id not found in CMMS for failure_type_id: {ftid}"
                session.commit()
                return
            aft_id, crit = aft_map_by_key[key]
            asset_failure_type_ids.append(int(aft_id))
            if not ensure_failure_type(session, ftid):
                job.status = JobStatus.error
                job.error_message = f"Failure type not found in DB/CMMS: {ftid}"
                session.commit()
                return
            session.merge(AssetFailureType(
                asset_failure_type_id=int(aft_id),
                asset_id=asset_id,
                failure_type_id=int(ftid),
                criticality=crit,
            ))
        session.flush()

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

    prediction_future_time = compute_prediction_future_time(end, days_ahead=7)

    if job.endpoint_type == "asset_predict":
        prediction = predict(
            asset_id=asset_id,
            failure_start_time=start,
            maintenance_end_time=end,
            job_id=job.job_id
        )
        print(prediction)
        pr = max(0.0, min(0.99, float(prediction["predicted_reliability"])))
        pred_id = insert_prediction_row(session=session, predicted_reliability=pr,
                                        pred_time=source_time, pred_future_time=prediction_future_time,)
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
        pred_id = insert_prediction_row(session=session, aft_id=aft_id, predicted_reliability=pr,
                                        pred_time=source_time, pred_future_time=prediction_future_time,)
        out = {
            "prediction_id": pred_id,
            "asset_failure_type_ids": asset_failure_type_ids,
            "failure_type_probability": prediction["failure_type_probability"],
        }

        # JSON
        json_path = os.path.join(settings.DATA_DIR, f"{pred_id}.json")
        atomic_write_json(json_path, out)

        try:
            resp = asyncio.run(cmms_post_asset_failure_type_prediction_sync(out))
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
                                job2.retry_count = (job2.retry_count or 0) + 1
                                if job2.retry_count >= RETRY_LIMIT:
                                    job2.status = JobStatus.error
                                    job2.error_message = "Retry limit exceeded"
                                else:
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
