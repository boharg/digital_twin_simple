from fastapi import FastAPI, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import (AssetPredictIn, AssetPredictOut,
                      AssetFailureTypePredictIn, AssetFailureTypePredictOut,
                      AssetIn, MaintenanceListIn)
from .db import get_async_session, sync_engine
from .models import Base, PredictionJob, JobStatus
from .utils import request_sha256
import logging

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
    log.info("Incoming payload parsed: %s", body.model_dump())
    raw_payload = body.model_dump()                 # contains datetime objects
    req_hash = request_sha256(raw_payload)
    payload = body.model_dump(mode="json")          # or: payload = jsonable_encoder(body)
    # Idempotencia...
    existing = (await session.execute(
        select(PredictionJob).where(PredictionJob.request_hash == req_hash)
    )).scalar_one_or_none()
    if existing:
        log.info("Idempotent hit job_id=%s status=%s", existing.job_id, existing.status)
        return AssetPredictOut(prediction_id=str(existing.prediction_id) if existing.prediction_id else str(existing.job_id))
    job = PredictionJob(request_hash=req_hash, payload=payload, status=JobStatus.queued, endpoint_type="asset_predict")
    session.add(job)
    await session.commit()
    await session.refresh(job)
    log.info("Queued new job %s", job.job_id)
    return AssetPredictOut(prediction_id=str(job.job_id))


@app.post("/asset_failure_type_predict", response_model=AssetFailureTypePredictOut, status_code=status.HTTP_202_ACCEPTED)
async def asset_failure_type_predict(body: AssetFailureTypePredictIn, session: AsyncSession = Depends(get_async_session)):
    raw_payload = body.model_dump()
    req_hash = request_sha256(raw_payload)
    payload = body.model_dump(mode="json")          # or: payload = jsonable_encoder(body)
    existing = (await session.execute(
        select(PredictionJob).where(PredictionJob.request_hash == req_hash)
    )).scalar_one_or_none()
    if existing:
        return AssetFailureTypePredictOut(prediction_id=str(existing.prediction_id) if existing.prediction_id else str(existing.job_id))
    job = PredictionJob(request_hash=req_hash, payload=payload, status=JobStatus.queued, endpoint_type="asset_failure_type_predict")
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return AssetFailureTypePredictOut(prediction_id=str(job.job_id))


@app.post("/workrequest", response_model=AssetFailureTypePredictOut, status_code=status.HTTP_202_ACCEPTED)
async def workrequest(body: AssetFailureTypePredictIn, session: AsyncSession = Depends(get_async_session)):
    raw_payload = body.model_dump()
    req_hash = request_sha256(raw_payload)
    payload = body.model_dump(mode="json")          # or: payload = jsonable_encoder(body)
    existing = (await session.execute(
        select(PredictionJob).where(PredictionJob.request_hash == req_hash)
    )).scalar_one_or_none()
    if existing:
        return AssetFailureTypePredictOut(prediction_id=str(existing.prediction_id) if existing.prediction_id else str(existing.job_id))
    job = PredictionJob(request_hash=req_hash, payload=payload, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return AssetFailureTypePredictOut(prediction_id=str(job.job_id))


@app.get("/asset", response_model=AssetIn, status_code=status.HTTP_200_OK)
async def cmms_get_asset(asset_id: str, session: AsyncSession = Depends(get_async_session)):
    result = (await session.execute(
        select(Base).where(Base.asset_id == asset_id)
    )).scalar_one_or_none()
    if not result:
        return {"asset_id": asset_id, "asset_name": "Unknown"}
    return AssetIn(asset_id=result.asset_id, asset_name=result.asset_name)


@app.get("/maintenance_lists", response_model=MaintenanceListIn, status_code=status.HTTP_200_OK)
async def cmms_get_maintenance_list(maintenance_list_id: str, session: AsyncSession = Depends(get_async_session)):
    result = (await session.execute(
        select(Base).where(Base.maintenance_list_id == maintenance_list_id)
    )).scalar_one_or_none()
    if not result:
        return {"maintenance_list_id": maintenance_list_id, "maintenance_list_name": "Unknown"}
    return MaintenanceListIn(maintenance_list_id=result.maintenance_list_id, maintenance_list_name=result.maintenance_list_name)
