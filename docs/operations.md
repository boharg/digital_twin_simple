# digital_twin_simple – Runtime Documentation (updated)

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

## API Contracts

### POST `/asset_predict`

- Request model: `AssetPredictIn`
  - `operation_ids: list[int]`
  - `failure_start_time: datetime`
  - `maintenance_end_time: datetime`
  - `source_sys_time: datetime`
  - `asset_id: int`
  - `default_reliability: Optional[list[float]]`
- Response model: `AssetPredictOut`
  - `prediction_id: int`

### POST `/asset_failure_type_predict`

- Request model: `AssetFailureTypePredictIn`
  - same as `AssetPredictIn` plus `failure_type_ids: list[int]`
- Response model: `AssetFailureTypePredictOut`
  - `prediction_id: int`

### POST `/workrequest`

- Request model: same as `/asset_failure_type_predict`
- Response model: same as `/asset_failure_type_predict`
- Current limitation:
  - endpoint currently creates a `PredictionJob` without setting `endpoint_type`
  - `endpoint_type` is required in ORM/database model
  - worker has no dedicated `workrequest` processing branch

## End-to-End Flow

1. API validates request body via Pydantic.
2. API computes idempotency hash (`request_sha256`).
3. API checks `prediction_jobs` by `request_hash`.
4. If match exists, API returns the existing `prediction_id` (or `job_id`).
5. Otherwise API inserts a new job with status `queued`.
6. Worker loops continuously, claims one queued job using `FOR UPDATE SKIP LOCKED`, sets status `processing`.
7. Worker processes the job and writes outputs.
8. Worker updates job status to `done`, `not_found`, or `error`.

## Worker Details

## Claim/retry behavior

- `claim_one_job(session)` claims one queued row.
- `requeue_stuck_jobs(session)` requeues stale `processing` jobs up to `RETRY_LIMIT`; above limit, marks `error`.

## Validation and normalization

- Worker re-validates `job.payload`:
  - `AssetPredictIn` for `asset_predict`
  - `AssetFailureTypePredictIn` otherwise
- `failure_type_ids` is normalized to `list[int]`.

## Data preparation

- Asset existence:
  - DB lookup first
  - CMMS fallback: `cmms_get_assets`
- Failure type existence:
  - DB lookup first
  - CMMS fallback: `cmms_get_failure_types`
- Operation to maintenance mapping:
  - DB lookup: `operations_maintenance_list`
  - CMMS fallback: `cmms_get_operation_maintenance_lists`
- Asset to maintenance mapping:
  - DB lookup: `asset_maintenance_list`
  - CMMS fallback: `cmms_get_asset_maintenance_lists`

## `asset_failure_type_predict` specific checks

- `failure_type_ids` must be non-empty.
- Worker fetches `cmms_get_asset_failure_types(asset_id)`.
- Builds mapping `(asset_id, failure_type_id) -> asset_failure_type_id`.
- Upserts local `asset_failure_type` rows.
- Fetches and validates operation types from `cmms_get_asset_failure_type_operations`.

## Prediction and persistence

- Prediction horizon:
  - `prediction_future_time = maintenance_end_time + 7 days`
- Prediction function:
  - `predict(...)` from `app/predict.py`
  - current behavior:
    - no `failure_type_ids` -> `predicted_reliability = 1.0`
    - with `failure_type_ids` -> random `failure_type_probability` distribution and derived reliability
- Reliability is clamped to `[0.0, 0.99]` before DB insert.

Persisted outputs:

- DB: insert into `prediction`
- File: `<DATA_DIR>/<prediction_id>.json`
- CMMS POST:
  - `/asset_prediction` for `asset_predict`
  - `/asset_failure_type_prediction` for `asset_failure_type_predict`

## Job Status Lifecycle

- `queued` -> created by API
- `processing` -> claimed by worker
- `done` -> prediction persisted and CMMS POST succeeded
- `not_found` -> required external/internal data missing
- `error` -> validation or runtime/CMMS posting failure

## CMMS Endpoints Used by Code

GET:

- `/assets?asset_id=...`
- `/failures?failure_id=...`
- `/failure_types/{failure_type_id}`
- `/maintenance_lists?maintenance_list_id=...`
- `/operation_maintenance_lists?operation_id=...`
- `/asset_failure_types` or `/asset_failure_types/{asset_id}`
- `/asset_failure_type_asset_maintenance_lists?asset_id=...&failure_type=...&default_reliability=...`
- `/asset_maintenance_lists?asset_id=...`
- `/asset_failure_types_operations?asset_id=...&failure_type_id=...`

POST:

- `/asset_prediction`
- `/asset_failure_type_prediction`
- `/workrequest`

Header:

- `x-api-key: <CMMS_TOKEN>`

## Notes

- IDs are integer-based in the current code (not UUID-based).
- `predict()` currently does not use Weibull (`eta/beta`) to produce output values.
