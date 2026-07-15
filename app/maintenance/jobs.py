from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import JobStatus, PredictionJob
from ..schemas import AssetPredictIn
from ..utils import request_sha256


async def enqueue_prediction_job(
    session: AsyncSession,
    body: AssetPredictIn,
    endpoint_type: str = "asset_predict",
) -> int:
    """
    Létrehozza az /asset_predict kéréshez tartozó feldolgozási feladatot.

    Ugyanaz a teljes kérés nem hoz létre új jobot, hanem visszaadja
    a korábban létrehozott job_id értékét.
    """

    payload = body.model_dump(
        mode="json",
        by_alias=True,
    )

    request_hash = request_sha256(payload)

    existing_job_id = (
        await session.execute(
            select(PredictionJob.job_id).where(
                PredictionJob.request_hash == request_hash
            )
        )
    ).scalar_one_or_none()

    if existing_job_id is not None:
        return int(existing_job_id)

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

    session.add(job)

    try:
        await session.commit()
        await session.refresh(job)

    except IntegrityError:
        # Két azonos kérés egyidejű beérkezése esetén a request_hash
        # egyedi korlátozása miatt csak az egyik INSERT sikerül.
        await session.rollback()

        existing_job_id = (
            await session.execute(
                select(PredictionJob.job_id).where(
                    PredictionJob.request_hash == request_hash
                )
            )
        ).scalar_one_or_none()

        if existing_job_id is None:
            raise

        return int(existing_job_id)

    return int(job.job_id)