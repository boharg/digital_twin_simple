from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    JobStatus,
    PredictionJob,
)
from ..schemas import AssetPredictIn
from ..utils import request_sha256


RETRYABLE_STATUSES = {
    JobStatus.error,
    JobStatus.not_found,
}


async def reuse_existing_job(
    session: AsyncSession,
    job: PredictionJob,
) -> int:
    """
    Kezeli az ismételten beérkező, teljesen
    azonos kérést.

    queued, processing vagy done állapotnál
    csak visszaadja a meglévő job_id értéket.

    error vagy not_found állapotnál ugyanazt
    a jobot újra queued állapotba teszi.
    """

    if job.status in RETRYABLE_STATUSES:
        job.status = JobStatus.queued
        job.error_message = None
        job.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(
            job
        )

    return int(
        job.job_id
    )


async def find_job_by_request_hash(
    session: AsyncSession,
    request_hash: str,
) -> PredictionJob | None:
    """
    Megkeresi a request_hash értékhez tartozó
    prediction_jobs rekordot.
    """

    result = await session.execute(select(PredictionJob).where(PredictionJob.request_hash == request_hash))

    return result.scalar_one_or_none()


async def enqueue_prediction_job(
    session: AsyncSession,
    body: AssetPredictIn,
    endpoint_type: str = "asset_predict",
) -> int:
    """
    Létrehozza az /asset_predict kéréshez
    tartozó feldolgozási feladatot.

    Ugyanaz a teljes kérés nem hoz létre új
    prediction_jobs rekordot.
    """

    payload = body.model_dump(
        mode="json",
        by_alias=True,
    )

    request_hash = request_sha256(
        payload
    )

    existing_job = await find_job_by_request_hash(
        session=session,
        request_hash=request_hash,
    )

    if existing_job is not None:
        return await reuse_existing_job(
            session=session,
            job=existing_job,
        )

    now = datetime.utcnow()

    job = PredictionJob(
        workorder_id=body.workorder_id,
        request_hash=request_hash,
        payload=payload,
        status=JobStatus.queued,
        endpoint_type=endpoint_type,
        error_message=None,
        created_at=now,
        updated_at=now,
    )

    session.add(
        job
    )

    try:
        await session.commit()
        await session.refresh(
            job
        )

    except IntegrityError:
        # Két teljesen azonos kérés egyidejű
        # beérkezésekor csak az egyik INSERT
        # lehet sikeres.
        await session.rollback()

        existing_job = (
            await find_job_by_request_hash(
                session=session,
                request_hash=request_hash,
            )
        )

        if existing_job is None:
            raise

        return await reuse_existing_job(
            session=session,
            job=existing_job,
        )

    return int(
        job.job_id
    )
