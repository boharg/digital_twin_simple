# digital_twin_simple – Runtime Documentation (call order, data flow)

## Main Components

- API (FastAPI, async): `app/main.py`
- Data schemas (Pydantic): `app/schemas.py`
- DB connections: async for API, sync for worker: `app/db.py`
- ORM models and queue table: `app/models.py`
- Worker (DB-queue processor): `app/worker.py`
- Prediction logic: `app/predict.py`
- CMMS client calls (HTTP): `app/cmms.py`
- Utilities: idempotency hash, atomic JSON write: `app/utils.py`

## Flow Overview

1) API receives request (`POST /asset_predict` or `POST /asset_failure_type_predict`):
   - Parse and validate body via Pydantic model (FastAPI does this):
     - `/asset_predict` → `app/schemas.py` (`AssetPredictIn`)
     - `/asset_failure_type_predict` → `app/schemas.py` (`AssetFailureTypePredictIn`)
   - Compute idempotency hash: `app/main.py` (`request_sha256(raw_payload)`), `app/utils.py`
     - Input: dict with `datetime` and `UUID`.
     - Output: `str` SHA-256 hex digest.
   - Check existing job (`app/main.py`): `session.execute(select(PredictionJob).where(PredictionJob.request_hash == req_hash))`
     - If found: respond with `prediction_id` of existing job/prediction.
   - Else enqueue new job: `PredictionJob(request_hash=req_hash, payload=payload, status=queued, endpoint_type=...)` – `app/main.py`
     - `payload` is Pydantic `.model_dump(mode="json")` (datetimes/UUIDs serialized) – `app/main.py`
   - Respond 202 with `prediction_id = job.job_id` – `app/main.py` (or line-equivalent for other endpoint).

2) Worker loop (poll and claim):
   - Loop: `main()` runs forever, calling `session_scope()`
   - Claim job: `claim_one_job(session)`
     - SQL: select next `status='queued'` row with `FOR UPDATE SKIP LOCKED`.
     - Sets `status='processing'`, commits, refreshes; returns `PredictionJob` or `None`.

3) Worker processing (common pre-steps): `process_job(session, job)`
   - Re-validate payload: `p = AssetPredictIn(**job.payload)`
     - Input: `job.payload` (dict from queue), Output: Pydantic model `p`.
   - Extract fields:
     - `asset_id: str`, `start: datetime`, `end: datetime`, `source_time: datetime`.
     - `failure_type_id: str | 'None'`
     - `operation_ids: list[str]`.
   - Ensure base data:
     - `ensure_asset(session, asset_id)`
       - If not in DB: calls `cmms_get_asset(asset_id)` (async)
       - On success: `session.merge(Asset(...))`, commit; returns `True`. Else `False`.
     - `ensure_failure_type(session, failure_type_id)`
       - If not in DB: calls `cmms_get_failure_type(failure_type_id)`
       - On success: merge + commit; returns `True`. Else `False`.
   - Ensure maintenance-list links per operation:
     - `has_maintenanace_list(session, op_id)`→ returns `bool`.
     - OR `ensure_operation_maintenanace_lists(session, op_id)` → fetch from CMMS and upsert; returns `bool`.
   - Resolve AFT (asset-failure-type) and AML (asset-maintenance-list):
     - `aft_id = ensure_asset_failure_type_id(session, asset_id, failure_type_id)` → returns `str | None`.
     - `aml_ids = ensure_asset_maintenance_lists(session, asset_id)` → returns `list[str]` of `maintenance_list_id`.
     - `amlaft_ml_ids = ensure_asset_maintenance_lists_asset_failure_type(session, asset_id, failure_type_id)` → ensures AFT↔AML rows and returns `list[str]` of maintenance_list IDs.
   - Prediction horizon: `prediction_future_time = compute_prediction_future_time(end, days_ahead=7)`

4) Worker prediction branch and persistence:
   - If `job.endpoint_type == 'asset_predict'`:
     - `value = predict_reliability(prediction_future_time, start, end, source_time, eta_value=None, beta_value=None, default_reliability=p.get("default_reliability"))`
       - Output: `float` in [0, 1], 6 decimals.
     - `pred_id = uuid.uuid4()`; `out = {"prediction_id": str(pred_id), "predicted_reliability": float(value)}`
     - Persist outputs:
       - JSON: `atomic_write_json(path, out)` into `settings.DATA_DIR`
       - DB: `insert_prediction_row(session, pred_id, aft_id, value, source_time, prediction_future_time)`
       - CMMS: `cmms_post_asset_prediction_sync(out)`. On error: set `job.status='error'`, store message
   - If `job.endpoint_type == 'asset_failure_type_predict'`:
     - Same steps, CMMS call is `cmms_post_asset_failure_type_prediction_sync(out)`
   - Finish: `job.status='done'`, `job.prediction_id=pred_id`, commit

5) Outputs summary:
   - File: `<DATA_DIR>/<prediction_id>.json` with `{ prediction_id, predicted_reliability }`
   - DB: `prediction` row with `asset_failure_type_id`, `predicted_reliability`, `time=source_sys_time`, `prediction_future_time`
   - CMMS: synchronous POST; response recorded in logs; failures mark job as `error`.

## Endpoints and Call Order

### POST `/asset_predict`

- Definition: `app/main.py`
- Input (Pydantic): `AssetPredictIn` (`app/schemas.py`)
  - `operation_id: list[UUID]`
  - `failure_start_time: datetime`
  - `maintenance_end_time: datetime`
  - `source_sys_time: datetime`
  - `asset_id: UUID`
  - `default_reliability: Optional[list[float]]`
- Steps in the API:
  - `request_sha256(body.model_dump())` → `req_hash` (`app/main.py`–`app/main.py`)
  - Idempotency: SELECT by `request_hash` from `prediction_jobs` (`app/main.py`)
  - If no existing record: `PredictionJob(request_hash=req_hash, payload=payload, status=queued, endpoint_type="asset_predict")` → INSERT → 202 response `prediction_id=job.job_id` (`app/main.py`)

Worker processing (detailed below): for `endpoint_type == "asset_predict"` it predicts and calls the CMMS `asset_prediction` (`app/worker.py`)

### POST `/asset_failure_type_predict`

- Definition: `app/main.py`
- Input: `AssetFailureTypePredictIn` (`app/schemas.py`)
    - `operation_id: list[UUID]`
  - `failure_start_time: datetime`
  - `maintenance_end_time: datetime`
  - `source_sys_time: datetime`
  - `asset_id: UUID`
  - `failure_type_id: UUID`
  - `default_reliability: Optional[list[float]]`
- API steps are identical to `asset_predict`, with `endpoint_type="asset_failure_type_predict"` (`app/main.py`)
- Worker takes the appropriate branch and calls CMMS `asset_failure_type_prediction` (`app/worker.py`)

## Worker – Steps and Calls

Entry and loop:

- `main()` → infinite loop, uses `session_scope()` per iteration (`app/worker.py`)
- `session_scope()` context manager ensures commit/rollback/close (`app/worker.py`)
- `claim_one_job(session)` picks one `queued` record with SKIP LOCKED, sets `status=processing` (`app/worker.py`)
- `process_job(session, job)` performs actual processing (`app/worker.py`)

process_job main steps and function calls:

1) Payload validation: `p = AssetPredictIn(**job.payload)` (`app/worker.py`)

2) Extract fields:
   - `asset_id = str(p.asset_id)` (`app/worker.py`)
   - `start = p.failure_start_time`, `end = p.maintenance_end_time`, `source_time = p.source_sys_time` (`app/worker.py`)
   - `failure_type_id = str(p.failure_type_id)` (`app/worker.py`)
   - `operation_ids = [str(...)]` (`app/worker.py`)

3) Ensure base data:
   - `ensure_asset(session, asset_id)` → if missing in DB, pulls from CMMS (`cmms_get_asset`) then `merge` into `Asset` (`app/worker.py` - `app/cmms.py`).
   - `ensure_failure_type(session, failure_type_id)` → if missing in DB, pulls from CMMS (`cmms_get_failure_type`) then `merge` into `FailureType` (`app/worker.py`- `app/cmms.py:39`).

4) Check related data:
   - Optional timescale/gamma check (it will be necessary for prediction, currently commented out) (`app/worker.py`), query: `has_gamma_data()` (`app/worker.py`)
   - Maintenance lists for each `operation_id`:
     - `has_maintenanace_list(session, op_id)` or
     - `ensure_operation_maintenanace_lists(session, op_id)` → if not in DB, fetch from CMMS and upsert mappings (returns `bool`) (`app/worker.py` - `app/cmms.py:69`).

5) Resolve key IDs and ensure relations:
   - `aft_id = ensure_asset_failure_type_id(session, asset_id, failure_type_id)` (`app/worker.py`)
   - `ensure_asset_maintenance_lists(session, asset_id)` → if missing, fetch from CMMS and upsert `asset_maintenance_list` (`app/worker.py` – `app/cmms.py`).
   - `ensure_asset_maintenance_lists_asset_failure_type(session, asset_id, failure_type_id)` → create missing AFT↔AML mappings (default_reliability=1), return ML IDs (`app/worker.py`)

6) Prediction horizon:
   - `prediction_future_time = compute_prediction_future_time(end, days_ahead=7)` (`app/worker.py` - `app/predict.py`)

7) Prediction and outputs (per-branch):
   - Common prediction call: `predict_reliability(...)` (`app/worker.py`), implementation in `app/predict.py`
   - `pred_id = uuid.uuid4()` and output JSON: `{ "prediction_id": str(pred_id), "predicted_reliability": float(value) }` (`app/worker.py`–`app/utils.py`)
   - DB insert into `prediction` table: `insert_prediction_row(...)` (`app/worker.py`)
   - CMMS POST:
     - Asset level: `cmms_post_asset_prediction_sync(out)` (`app/worker.py`), endpoint in `app/cmms.py`
     - Asset-failure-type level: `cmms_post_asset_failure_type_prediction_sync(out)` (`app/worker.py`), endpoint in `app/cmms.py`.

8) Update job status: `job.status = done`, `job.prediction_id = pred_id` – (`app/worker.py`)

## Data Models and Tables (brief)

- Queue table: `PredictionJob` (`app/models.py`)
  - Fields: `job_id`, `request_hash`, `payload` (JSON), `status` (`queued|processing|done|not_found|error`), `endpoint_type`, `prediction_id`, `error_message`, `created_at`, `updated_at`.
- Domain tables: `Asset`, `FailureType`, `AssetFailureType`, `Sensor`, `SensorFailureType`, `Gamma`, `EtaBeta`, `Prediction`, `MaintenanceList`, `OperationsMaintenanceList`, `AssetMaintenanceList`, `AssetFailureTypeAssetMaintenanceList` (`app/models.py`)

## External CMMS Calls

- GET (async) (`app/cmms.py`):
  - `cmms_get_asset(asset_id)`
  - `cmms_get_failure_type(failure_type_id)`
  - `cmms_get_maintenance_list(maintenance_list_id)`
  - `cmms_get_operation_maintenance_lists(operation_id, maintenance_list_id?)`
  - `cmms_get_asset_maintenance_lists(asset_id)`
- POST (sync) (`app/cmms.py`):
  - `cmms_post_asset_prediction_sync(payload)`
  - `cmms_post_asset_failure_type_prediction_sync(payload)`
  - `cmms_post_workrequest(payload)`

All use `Authorization: Bearer <CMMS_TOKEN>` 
Base URL: `settings.CMMS_BASE_URL`

## Idempotency and JSON Persistence

- Idempotency hash: `request_sha256(payload)` (`app/utils.py`)
  - Dates in ISO-8601, UUIDs converted to strings, deterministic JSON sorting.
- Atomic JSON write: `atomic_write_json(path, data)` (`app/utils.py`)

## Error Handling and Statuses

- During `process_job`, possible outcomes:
  - `error`: payload validation error or CMMS POST error (`app/worker.py`)
  - `not_found`: missing base/relational data (asset, failure_type, mappings, etc.) – (`app/worker.py`)
  - `done`: prediction successful, `prediction_id` populated (`app/worker.py`)

## Quick Start Notes

- API: `uvicorn app.main:app --reload` – see `README.md`.
- Worker: `python -m app.worker`.
- Environment: `DATABASE_URL`, `ASYNC_DATABASE_URL`, `CMMS_BASE_URL`, `CMMS_TOKEN`, `DATA_DIR` (`app/settings.py`)

## Test cases


### `/asset_predict`

Request body:

{
    "operation_id": ["06fad7d5-1fc6-4bd6-b00d-da274663d88a"],
    "asset_id": "06fcd7d5-1fc6-4bc6-b00d-da274663d98d",
    "failure_start_time": "2025-10-02T10:00:00",
    "maintenance_end_time": "2025-08-16T11:00:00",
    "source_sys_time": "2025-10-16T09:00:00",
    "default_reliability": [0.90]
}

Step-by-step:
1) API parse → `AssetPredictIn` (datetimes and UUIDs parsed). Compute `req_hash = request_sha256(body)` – returns SHA-256 string. Insert `PredictionJob(status='queued', endpoint_type='asset_predict', payload=JSON)` – returns `job.job_id` (UUID). Respond `202 { "prediction_id": job_id }`.
2) Worker claims job: `claim_one_job()` → sets `status='processing'`.
3) `process_job()` re-validates payload. Extracts:
   - `asset_id='06fcd7d5-1fc6-4bc6-b00d-da274663d98d'`, `start`, `end`, `source_time`.
   - `failure_type_id` is missing in the request; current code evaluates `str(p.failure_type_id)` which yields the string `'None'`.
   - `operation_ids=["06fad7d5-1fc6-4bd6-b00d-da274663d88a"]`.
4) `ensure_asset(session, asset_id)` → True (DB or CMMS).
5) `ensure_failure_type(session, 'None')` → DB lookup fails; CMMS `cmms_get_failure_type('None')` returns 404 → returns False.
6) Worker sets `job.status='not_found'`, `job.error_message='Failure type not found in DB/CMMS'`, commits, and stops processing this job. No prediction is computed.

Result: The API initially returned `{ "prediction_id": job_id }`. After processing, the job row is updated with `prediction_id=<pred_id>`, and a prediction JSON file and DB row exist with reliability `0.9`.

### `/asset_failure_type_predict`

Request body:

{
    "operation_id": ["06fad7d5-1fc6-4bd6-b00d-da274663d88a"],
    "asset_id": "06fcd7d5-1fc6-4bc6-b00d-da274663d98d",
    "failure_start_time": "2025-10-02T10:00:00",
    "maintenance_end_time": "2025-08-16T11:00:00",
    "source_sys_time": "2025-10-16T09:00:00",
    "failure_type_id": "702ab05a-7427-4a36-a298-0331bd56510a",
    "default_reliability": [0.90]
}

Step-by-step:
1) API parse → `AssetFailureTypePredictIn`. Compute `req_hash = request_sha256(body)`; upsert `PredictionJob(status='queued', endpoint_type='asset_failure_type_predict')`; respond `202 { "prediction_id": job_id }`.
2) Worker claims job → `status='processing'`.
3) `process_job()` extracts:
   - `asset_id='06fcd7d5-1fc6-4bc6-b00d-da274663d98d'`,
   - `start='2025-10-02T10:00:00'`, `end='2025-08-16T11:00:00'`, `source_time='2025-10-16T09:00:00'`,
   - `failure_type_id='702ab05a-7427-4a36-a298-0331bd56510a'`,
   - `operation_ids=['06fad7d5-1fc6-4bd6-b00d-da274663d88a']`.
4) Ensure base data:
   - `ensure_asset(session, asset_id)` → True (DB or via `cmms_get_asset`).
   - `ensure_failure_type(session, failure_type_id)` → True (DB or via `cmms_get_failure_type`).
5) Ensure operation → maintenance_list mapping:
   - For each op: `has_maintenanace_list(session, op_id)` or `ensure_operation_maintenanace_lists(session, op_id)`.
   - If neither returns truthy for all ops → job `not_found` with message.
6) Resolve relationships:
   - `aft_id = ensure_asset_failure_type_id(session, asset_id, failure_type_id)` → UUID string.
   - `aml_ids = ensure_asset_maintenance_lists(session, asset_id)` → list of maintenance_list UUIDs (strings), creating rows from CMMS if missing.
   - `amlaft_ml_ids = ensure_asset_maintenance_lists_asset_failure_type(session, asset_id, failure_type_id)` → ensures AFT↔AML rows; returns maintenance_list UUIDs.
7) Compute horizon:
   - `prediction_future_time = end + 7 days` → `2025-08-23T11:00:00` (`app/predict`)
8) Predict:
   - `predict_reliability(prediction_future_time, start, end, source_time, eta_value=None, beta_value=None, default_reliability=[0.90])` → returns `0.9` (`app/predict.py`)
9) Persist:
   - `pred_id = <new UUID>`.
   - JSON file: `prediction_out/<pred_id>.json` with `{ "prediction_id": "<pred_id>", "predicted_reliability": 0.9 }` (`app/worker.py`).
   - DB insert: `insert_prediction_row(session, pred_id, aft_id, 0.9, source_time, prediction_future_time)` → new row in `prediction` (`app/models.py`)
   - CMMS POST: `cmms_post_asset_failure_type_prediction_sync({prediction_id, predicted_reliability})` → expect JSON or status; on error, marks job `error` (`app/cmms.py`)
10) Finish:
   - `job.status='done'`, `job.prediction_id=pred_id`, commit.

Result: The API initially returned `{ "prediction_id": job_id }`. After processing, the job row is updated with `prediction_id=<pred_id>`, and a prediction JSON file and DB row exist with reliability `0.9`.
