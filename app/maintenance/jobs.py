from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AssetFailureType, Prediction, PredictionJob, JobStatus
from ..utils import request_sha256


async def _next_prediction_id(session: AsyncSession) -> int:
    next_id = (
        await session.execute(
            select(func.coalesce(func.max(Prediction.prediction_id), 0) + 1)
        )
    ).scalar_one()
    return int(next_id)


async def _resolve_asset_failure_type_id(session: AsyncSession, body, endpoint_type: str) -> int:
    query = select(AssetFailureType.asset_failure_type_id).where(
        AssetFailureType.asset_id == int(body.asset_id)
    )

    failure_type_ids = getattr(body, "failure_type_ids", None)
    if endpoint_type == "asset_failure_type_predict" and failure_type_ids:
        query = query.where(AssetFailureType.failure_type_id == int(failure_type_ids[0]))

    aft_id = (await session.execute(query.limit(1))).scalar_one_or_none()
    if aft_id is None:
        raise ValueError("asset_failure_type_id is required before enqueue; sync asset_failure_types first")
    return int(aft_id)


async def enqueue_prediction_job(
    session: AsyncSession,
    body,
    endpoint_type: str,
) -> int:
    raw_payload = body.model_dump()
    req_hash = request_sha256(raw_payload)
    payload = body.model_dump(mode="json")

    existing = (
        await session.execute(
            select(PredictionJob).where(
                PredictionJob.request_hash == req_hash,
                PredictionJob.endpoint_type == endpoint_type
            )
        )
    ).scalar_one_or_none()

    if existing:
        return existing.prediction_id or existing.job_id

    prediction = Prediction(
        prediction_id=await _next_prediction_id(session),
        asset_id=int(body.asset_id),
        asset_failure_type_id=await _resolve_asset_failure_type_id(session, body, endpoint_type),
    )
    session.add(prediction)
    await session.flush()

    now = datetime.utcnow()
    job = PredictionJob(
        request_hash=req_hash,
        payload=payload,
        status=JobStatus.queued,
        endpoint_type=endpoint_type,
        prediction_id=prediction.prediction_id,
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job.prediction_id
