import logging

from fastapi import Depends, FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_async_session
from .maintenance.jobs import enqueue_prediction_job
from .schemas import AssetPredictAccepted, AssetPredictIn


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")


app = FastAPI(
    title="Asset Prediction API",
    version="1.0.0",
)


@app.post(
    "/asset_predict",
    response_model=AssetPredictAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def asset_predict(
    body: AssetPredictIn,
    session: AsyncSession = Depends(
        get_async_session
    ),
) -> AssetPredictAccepted:
    job_id = await enqueue_prediction_job(
        session=session,
        body=body,
        endpoint_type="asset_predict",
    )

    log.info(
        "Prediction job accepted: "
        "job_id=%s, workorder_id=%s, sf_asset_id=%s",
        job_id,
        body.workorder_id,
        body.sf_asset_id,
    )

    return AssetPredictAccepted(
        job_id=job_id
    )