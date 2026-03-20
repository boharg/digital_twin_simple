# digital_twin_simple - Mukodesi dokumentacio

## Fo komponensek

- API (FastAPI, async): `app/main.py`
- Adatsemak (Pydantic): `app/schemas.py`
- DB kapcsolatok: `app/db.py`
- ORM modellek: `app/models.py`
- Worker (DB queue fogyaszto): `app/worker.py`
- Predikcios logika: `app/predict.py`
- CMMS kliens: `app/cmms.py`
- Segedek (idempotencia hash, atomikus JSON iras): `app/utils.py`
- Beallitasok: `app/settings.py`

## API vegpontok

### POST `/asset_predict`

- Input: `AssetPredictIn`
- Kimenet: `AssetPredictOut` (`prediction_id: int`)

Mukodes:
- Idempotencia hash keszul a request body-bol (`request_hash`).
- Ha van azonos hash-u job, ugyanazt az azonosito adja vissza.
- Kulonben `prediction_jobs` rekord jon letre `endpoint_type="asset_predict"` ertekkel.

### POST `/asset_failure_type_predict`

- Input: `AssetFailureTypePredictIn`
- Kimenet: `AssetFailureTypePredictOut` (`prediction_id: int`)

Mukodes:
- Idempotens queue-olas `request_hash` alapjan.
- Uj job `endpoint_type="asset_failure_type_predict"`.

## Folyamat attekintes

1. API hivashoz payload erkezik.
2. FastAPI/Pydantic validalja a payloadot.
3. API `request_hash` erteket szamol.
4. API meglevo jobot keres a hash alapjan.
5. Ha nincs talalat, uj rekord jon letre a `prediction_jobs` tablaban (`queued`).
6. A worker folyamatosan poll-ol, es `FOR UPDATE SKIP LOCKED` segitsegevel claim-eli a soron kovetkezo jobot.
7. A worker `processing` statuszra allit, majd lefuttatja a `process_job` logikat.
8. Kimenet: DB insert a `prediction` tablaba, JSON fajl a `DATA_DIR` konyvtarba, CMMS POST.
9. Job statusz vege: `done`, `not_found`, vagy `error`.

## Worker logika roviden

Claim es retry:

- `claim_one_job` kivalaszt egy `queued` sort es `processing` statuszra allitja.
- `requeue_stuck_jobs` a 120 masodpercnel regebbi `processing` jobokat visszateszi `queued`-ba, ha `retry_count < 5`.
- A retry limit folott `error` statusz jon `Retry limit exceeded` uzenettel.

Payload ujravalidacio:

- `asset_predict` eseten `AssetPredictIn`.
- `asset_failure_type_predict` eseten `AssetFailureTypePredictIn`.

Alapadatok biztositasa:

- Asset ellenorzes DB-ben, szukseg eseten CMMS-bol betoltes (`cmms_get_assets`).
- Failure type ellenorzes es CMMS fallback (`cmms_get_failure_types`).

## `asset_failure_type_predict` specifikus elokeszites

- `failure_type_ids` nem lehet ures.
- CMMS-bol lekeri az `asset_failure_types` adatokat.
- `asset_id + failure_type_id -> asset_failure_type_id` lekepest epit.
- Upserteli az `asset_failure_type` tablakat.
- CMMS `asset_failure_type_operations` alapjan ellenorzi az operation tipust (`BOTH`, `CORRECTIVE`, `PREVENTIVE`).

## Operation es maintenance list ellenorzes

- Minden `operation_id`-hoz biztosit helyi `operation` rekordot (idempotens insert).
- Ellenorzi vagy betolti az operation-maintenance mappingokat.
- DB: `operations_maintenance_list`.
- CMMS fallback: `cmms_get_operation_maintenance_lists`.

## Asset es AFT-AML relaciok

- Biztositja az `asset_maintenance_list` sorokat (`cmms_get_asset_maintenance_lists` fallback).
- `asset_failure_type_predict` eseten biztositja az `asset_failure_type_asset_maintenance_list` relaciokat.

## Predikcio es perzisztalas

- Horizont: `prediction_future_time = maintenance_end_time + 7 nap`.
- Predikcio: `predict(...)`.
- `asset_predict` eseten a jelenlegi implementacio `predicted_reliability = 1.0` erteket ad.
- `asset_failure_type_predict` eseten random valoszinusegi eloszlast general a megadott `failure_type_ids` listara.
- `predicted_reliability` clampelve van `0.0..0.99` koze.
- DB insert: `prediction` tabla.
- JSON mentes: `<DATA_DIR>/<prediction_id>.json`.
- CMMS POST: `/asset_prediction` vagy `/asset_failure_type_prediction`.

## CMMS integracio

GET:

- `/assets?asset_id=...`
- `/failure_types/{failure_type_id}`
- `/maintenance_lists?maintenance_list_id=...`
- `/operation_maintenance_lists?operation_id=...`
- `/asset_failure_types` vagy `/asset_failure_types/{asset_id}`
- `/asset_failure_types_operations?asset_id=...&failure_type_id=...`
- `/asset_maintenance_lists?asset_id=...`

POST:

- `/asset_prediction`
- `/asset_failure_type_prediction`

Auth header:

- `x-api-key: <CMMS_TOKEN>`

Timeoutok:

- total 10s, connect 5s, read 5s

## Idempotencia

- `request_hash` determinisztikus JSON hash (`sort_keys=True`).
- datetime mezok ISO formatumban kerulnek hashelesre.

## Ismert korlatok

- A predikcios logika jelenleg placeholder jellegu.
- `default_reliability` parametert az API fogadja, de a `predict()` meg nem hasznalja.
- Csak a `prediction_jobs` tabla jon letre automatikusan startupkor; mas tablaknak letezniuk kell.
