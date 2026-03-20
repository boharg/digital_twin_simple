# digital_twin_simple - Runtime Documentation (updated)

This document reflects the current implementation in the repository.

## Main Components

- API (FastAPI, async): `app/main.py`
- Data schemas (Pydantic): `app/schemas.py`
- DB setup (async API + sync worker): `app/db.py`
- ORM models: `app/models.py`
- Worker (DB queue processor): `app/worker.py`
- Prediction logic: `app/predict.py`
- CMMS integration: `app/cmms.py`
- Utilities: `app/utils.py`
- Settings/env: `app/settings.py`

## API Contracts

### POST `/asset_predict`

- Request model: `AssetPredictIn`
- Response model: `AssetPredictOut`
- Behavior: idempotent queueing via `request_hash`, returns `prediction_id`.

### POST `/asset_failure_type_predict`

- Request model: `AssetFailureTypePredictIn`
- Response model: `AssetFailureTypePredictOut`
- Behavior: idempotent queueing via `request_hash`, returns `prediction_id`.

## End-to-End Flow

1. API validates request body via Pydantic.
2. API computes idempotency hash (`request_hash`).
3. API checks `prediction_jobs` by `request_hash`.
4. If match exists, API returns existing `prediction_id` or `job_id`.
5. Otherwise API inserts a new job with status `queued` and `endpoint_type`.
6. Worker claims one queued job using `FOR UPDATE SKIP LOCKED`, sets status `processing`.
7. Worker processes the job and writes outputs.
8. Worker updates job status to `done`, `not_found`, or `error`.

## Worker Details

Claim and retry behavior:

- `claim_one_job(session)` claims one queued row and marks it `processing`.
- `requeue_stuck_jobs(session)` requeues stale `processing` jobs older than 120 seconds if `retry_count < 5`.
- Above the retry limit, jobs are marked `error` with `Retry limit exceeded`.

Validation and normalization:

- Worker re-validates `job.payload` using `AssetPredictIn` or `AssetFailureTypePredictIn`.
- `failure_type_ids` is normalized to `list[int]`.

Data preparation:

- Asset existence: DB lookup first, CMMS fallback `cmms_get_assets`.
- Failure type existence: DB lookup first, CMMS fallback `cmms_get_failure_types`.
- Operation to maintenance mapping: DB `operations_maintenance_list`, CMMS fallback `cmms_get_operation_maintenance_lists`.
- Asset to maintenance mapping: DB `asset_maintenance_list`, CMMS fallback `cmms_get_asset_maintenance_lists`.

`asset_failure_type_predict` specific checks:

- `failure_type_ids` must be non-empty.
- Worker fetches `cmms_get_asset_failure_types(asset_id)`.
- Builds mapping `(asset_id, failure_type_id) -> asset_failure_type_id`.
- Upserts local `asset_failure_type` rows.
- Fetches and validates operation types from `cmms_get_asset_failure_type_operations`.

Prediction and persistence:

- Prediction horizon: `prediction_future_time = maintenance_end_time + 7 days`.
- Prediction function: `predict(...)` from `app/predict.py`.
- Current behavior: `asset_predict` returns reliability 1.0, failure-type mode returns random probabilities.
- `predicted_reliability` is clamped to `[0.0, 0.99]` before DB insert.

Persisted outputs:

- DB: insert into `prediction`.
- File: `DATA_DIR/<prediction_id>.json`.
- CMMS POST: `/asset_prediction` or `/asset_failure_type_prediction`.

## Job Status Lifecycle

- `queued` -> created by API
- `processing` -> claimed by worker
- `done` -> prediction persisted and CMMS POST succeeded
- `not_found` -> required external/internal data missing
- `error` -> validation or runtime/CMMS posting failure

## CMMS Endpoints Used by Code

GET:

- `/assets?asset_id=...`
- `/failure_types/{failure_type_id}`
- `/maintenance_lists?maintenance_list_id=...`
- `/operation_maintenance_lists?operation_id=...`
- `/asset_failure_types` or `/asset_failure_types/{asset_id}`
- `/asset_failure_types_operations?asset_id=...&failure_type_id=...`
- `/asset_maintenance_lists?asset_id=...`

POST:

- `/asset_prediction`
- `/asset_failure_type_prediction`

Header:

- `x-api-key: <CMMS_TOKEN>`

Timeouts:

- total 10s, connect 5s, read 5s

## Notes

- IDs are integer-based in the current code.
- `default_reliability` is accepted but not used in prediction logic.
- Only `prediction_jobs` is auto-created at startup; other tables must exist.
