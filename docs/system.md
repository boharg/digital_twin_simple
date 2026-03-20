# System Operation Overview

This document describes the current runtime behavior of the system and the main data flows.
It complements `docs/mukodes.md` and `docs/operations.md`.

## Components

- API service (FastAPI): `app/main.py`
- Worker (DB queue consumer): `app/worker.py`
- CMMS client (HTTP): `app/cmms.py`
- ORM models: `app/models.py`
- Schemas (Pydantic): `app/schemas.py`
- Prediction logic: `app/predict.py`
- Utilities: `app/utils.py`
- Settings/env: `app/settings.py`

## High-level Flow

1. Client sends a POST to the API (`/asset_predict` or `/asset_failure_type_predict`).
2. API validates payload, computes a deterministic `request_hash`, and checks idempotency.
3. If no existing job matches the hash, API inserts a row into `prediction_jobs` with status `queued`.
4. Worker polls the DB, claims one job (`FOR UPDATE SKIP LOCKED`), marks it `processing`.
5. Worker prepares data by loading missing entities from CMMS and DB.
6. Worker runs prediction logic, stores results, writes JSON, posts to CMMS.
7. Worker marks the job `done`, `not_found`, or `error`.

## Queue and Job Lifecycle

- `queued`: created by API
- `processing`: claimed by worker
- `done`: prediction stored and CMMS POST succeeded
- `not_found`: required data missing (asset, failure type, mappings, or CMMS payload)
- `error`: validation or CMMS POST failure

Queue table: `public.prediction_jobs`

Retry behavior:

- Stuck `processing` jobs older than 120 seconds are re-queued if `retry_count < 5`.
- Above the retry limit, they are marked `error` with `Retry limit exceeded`.
- The worker runs requeue checks about every 30 seconds.

## Endpoint Behavior

### POST `/asset_predict`

- Input: `AssetPredictIn`
- Action: queues a job with `endpoint_type=asset_predict`
- Output: `{ "prediction_id": <job_id or existing prediction_id> }`

Worker steps:

1. Ensure asset exists (DB or CMMS).
2. Ensure operation -> maintenance_list mappings exist (DB or CMMS).
3. Ensure asset -> maintenance_list mappings exist (DB or CMMS).
4. Compute prediction and store in `prediction` table.
5. Write JSON to `DATA_DIR/<prediction_id>.json`.
6. POST result to CMMS `/asset_prediction`.

### POST `/asset_failure_type_predict`

- Input: `AssetFailureTypePredictIn`
- Action: queues a job with `endpoint_type=asset_failure_type_predict`
- Output: `{ "prediction_id": <job_id or existing prediction_id> }`

Worker steps:

1. Ensure asset exists (DB or CMMS).
2. Ensure `failure_type_ids` is non-empty.
3. Fetch CMMS `asset_failure_types` for the asset to map `failure_type_id -> asset_failure_type_id`.
4. Upsert `asset_failure_type` rows in DB (including CMMS-provided `asset_failure_type_id`).
5. Validate CMMS `asset_failure_type_operations` and operation types.
6. Ensure operation -> maintenance_list mappings exist (DB or CMMS).
7. Ensure asset -> maintenance_list mappings exist (DB or CMMS).
8. Ensure asset_failure_type -> asset_maintenance_list mappings exist (DB, derived from asset AMLs).
9. Compute prediction and store in `prediction` table.
10. Write JSON to `DATA_DIR/<prediction_id>.json`.
11. POST result to CMMS `/asset_failure_type_prediction` including `prediction_id`, `asset_failure_type_ids`, and `failure_type_probability`.

## Prediction Logic

- Prediction horizon: `prediction_future_time = maintenance_end_time + 7 days`.
- Current behavior for `asset_predict`: `predicted_reliability = 1.0`.
- Current behavior for `asset_failure_type_predict`: random probability distribution and derived reliability.
- `predicted_reliability` is clamped to `0.0..0.99` before inserting into DB.

## CMMS Integration

### CMMS GET calls

- `/assets?asset_id=...`
- `/failure_types/{failure_type_id}`
- `/maintenance_lists?maintenance_list_id=...`
- `/operation_maintenance_lists?operation_id=...`
- `/asset_failure_types` or `/asset_failure_types/{asset_id}`
- `/asset_failure_types_operations?asset_id=...&failure_type_id=...`
- `/asset_maintenance_lists?asset_id=...`

### CMMS POST calls

- `/asset_prediction`
- `/asset_failure_type_prediction`

Auth header: `x-api-key: <CMMS_TOKEN>`

Timeouts: total 10s, connect 5s, read 5s.

## Data Persistence

- `prediction_jobs`: queue and status tracking
- `prediction`: prediction results
- `asset`, `failure_type`, `asset_failure_type`: master data, loaded from CMMS when missing
- mapping tables: `asset_maintenance_list`, `operations_maintenance_list`, `asset_failure_type_asset_maintenance_list`

## Notes / Assumptions

- All IDs are integer-based in the current codebase.
- `default_reliability` is accepted by the API but not used in prediction logic.
- Only the `prediction_jobs` table is auto-created on startup; other tables are expected to exist.
