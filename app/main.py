from fastapi import FastAPI, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import (AssetPredictIn, AssetPredictOut,
                      AssetFailureTypePredictIn, AssetFailureTypePredictOut)
from .db import get_async_session, sync_engine
from .models import Base, PredictionJob
import logging
from .jobs import enqueue_prediction_job

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Asset Prediction API (DB-queue, no Docker)", version="1.0.0")


# Csak a saját job táblát hozzuk létre, ha hiányzik.
@app.on_event("startup")
async def on_startup():
    def _create_jobs_table():
        Base.metadata.create_all(bind=sync_engine, tables=[PredictionJob.__table__])
    # Szinkron blokkot futtatunk külön threadben
    import anyio
    await anyio.to_thread.run_sync(_create_jobs_table)


@app.post("/asset_predict", response_model=AssetPredictOut, status_code=status.HTTP_202_ACCEPTED)
async def asset_predict(body: AssetPredictIn, session: AsyncSession = Depends(get_async_session)):
    prediction_id = await enqueue_prediction_job(session, body, "asset_predict")
    return AssetPredictOut(prediction_id=prediction_id)


@app.post("/asset_failure_type_predict", response_model=AssetPredictOut, status_code=status.HTTP_202_ACCEPTED)
async def asset_failure_type_predict(body: AssetPredictIn, session: AsyncSession = Depends(get_async_session)):
    prediction_id = await enqueue_prediction_job(session, body, "asset_failure_type_predict")
    return AssetPredictOut(prediction_id=prediction_id)


@app.post("/workrequest", response_model=AssetFailureTypePredictOut, status_code=status.HTTP_202_ACCEPTED)
async def workrequest(body: AssetFailureTypePredictIn, session: AsyncSession = Depends(get_async_session)):
    prediction_id = await enqueue_prediction_job(session, body, "workrequest")
    return AssetFailureTypePredictOut(prediction_id=prediction_id)
