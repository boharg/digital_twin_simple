from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PredictionJob, JobStatus
from .utils import request_sha256


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

    job = PredictionJob(
        request_hash=req_hash,
        payload=payload,
        status=JobStatus.queued,
        endpoint_type=endpoint_type,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job.job_id
