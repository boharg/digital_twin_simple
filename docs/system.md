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

## High-level Flow

1. Client sends a POST to the API (`/asset_predict`, `/asset_failure_type_predict`, or `/workrequest`).
2. API validates payload and writes a job into `prediction_jobs` with status `queued`.
3. Worker polls the DB, claims a job (`FOR UPDATE SKIP LOCKED`), marks it `processing`.
4. Worker prepares data by loading missing entities from CMMS and DB.
5. Worker runs prediction logic, stores results, posts to CMMS, and marks the job `done`, `not_found`, or `error`.

## Queue and Job Lifecycle

- `queued`: created by API
- `processing`: claimed by worker
- `done`: prediction stored and CMMS POST succeeded
- `not_found`: required data missing (asset/failure_type/mappings/CMMS payload)
- `error`: validation or CMMS POST failure

Queue table: `public.prediction_jobs`

## Endpoint Behavior

### POST `/asset_predict`

- Input: `AssetPredictIn`
- Action: queues a job with `endpoint_type=asset_predict`
- Output: `{ "prediction_id": <job_id> }`

Worker steps:
- Ensure asset exists (DB or CMMS).
- Ensure maintenance lists for operations exist (DB or CMMS).
- Compute prediction and store in `prediction` table.
- POST result to CMMS `/asset_prediction`.

### POST `/asset_failure_type_predict`

- Input: `AssetFailureTypePredictIn`
- Action: queues a job with `endpoint_type=asset_failure_type_predict`
- Output: `{ "prediction_id": <job_id> }`

Worker steps:
- Ensure asset exists (DB or CMMS).
- Ensure failure types exist (DB or CMMS).
- Fetch CMMS `asset_failure_types` for the asset to map `failure_type_id -> asset_failure_type_id`.
- Upsert `asset_failure_type` rows in DB (including CMMS-provided `asset_failure_type_id`).
- Ensure maintenance list mappings.
- Compute prediction and store in `prediction` table.
- POST result to CMMS `/asset_failure_type_prediction` with:
  - `prediction_id`
  - `asset_failure_type_ids`
  - `failure_type_probability`

### POST `/workrequest`

Current implementation uses the same input schema as `/asset_failure_type_predict`, but has known gaps:

- Job insert does not set `endpoint_type`, which is required by the model.
- Worker has no explicit branch for `workrequest` processing.

## CMMS Integration

### CMMS GET calls

- `/assets?asset_id=...`
- `/failures?failure_id=...`
- `/failure_types/{failure_type_id}`
- `/maintenance_lists?maintenance_list_id=...`
- `/operation_maintenance_lists?operation_id=...`
- `/asset_maintenance_lists?asset_id=...`
- `/asset_failure_types` or `/asset_failure_types/{asset_id}`
- `/asset_failure_types_operations?asset_id=...&failure_type_id=...`
- `/asset_failure_type_asset_maintenance_lists?asset_id=...&failure_type=...&default_reliability=...`

### CMMS POST calls

- `/asset_prediction`
- `/asset_failure_type_prediction`
- `/workrequest`

All calls use the `x-api-key` header from `CMMS_TOKEN`.
Timeouts and response content-type are logged.

## Data Persistence

- `prediction_jobs`: queue and status tracking
- `prediction`: prediction results
- `asset`, `failure_type`, `asset_failure_type`: master data, loaded from CMMS when missing
- mapping tables: `asset_maintenance_list`, `operations_maintenance_list`, `asset_failure_type_asset_maintenance_list`

## Notes / Assumptions

- CMMS provides `asset_failure_type_id`; DB is configured to allow inserting it explicitly.
- `failure_type_ids` are provided by the API input.
- `asset_failure_type_ids` are derived from CMMS and used in CMMS POST payloads.
- Current code uses integer IDs in API payloads and DB mappings.
