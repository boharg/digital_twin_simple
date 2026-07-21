import logging

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_async_session
from .maintenance.jobs import enqueue_prediction_job
from .schemas import AssetPredictAccepted, AssetPredictIn
from .security import require_api_key


log = logging.getLogger("api")


app = FastAPI(
    title="Asset Prediction API",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    A FastAPI alapértelmezett 422-es validációs válaszát
    400 Bad Request válasszá alakítja.
    """

    log.warning(
        "Invalid request: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": jsonable_encoder(exc.errors()),
        },
    )


@app.post(
    "/asset_predict",
    response_model=AssetPredictAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Missing or invalid data in the request",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "API key is missing or invalid",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The prediction job could not be stored",
        },
    },
)
async def asset_predict(
    body: AssetPredictIn,
    session: AsyncSession = Depends(get_async_session),
) -> AssetPredictAccepted:
    """
    Fogadja a CMMS munkalapadatait, és sorba állítja
    a hozzá tartozó predikciós feladatot.
    """

    try:
        job_id = await enqueue_prediction_job(
            session=session,
            body=body,
            endpoint_type="asset_predict",
        )

    except SQLAlchemyError as exc:
        await session.rollback()

        log.exception(
            "Could not enqueue prediction job: "
            "workorder_id=%s, sf_asset_id=%s",
            body.workorder_id,
            body.sf_asset_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The prediction job could not be stored",
        ) from exc

    log.info(
        "Prediction job accepted: "
        "job_id=%s, workorder_id=%s, sf_asset_id=%s",
        job_id,
        body.workorder_id,
        body.sf_asset_id,
    )

    return AssetPredictAccepted(job_id=job_id)
