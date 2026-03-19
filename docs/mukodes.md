# digital_twin_simple – Működési dokumentáció (frissített)

Ez a dokumentum a jelenlegi kódbázis futás közbeni működését írja le.
Fókusz: hívási sorrend, adatáramlás, job-életciklus, és ismert korlátok.

## Fő komponensek

- API (FastAPI, async): `app/main.py`
- Adatsémák (Pydantic): `app/schemas.py`
- DB kapcsolatok: `app/db.py`
- ORM modellek: `app/models.py`
- Worker (DB queue fogyasztó): `app/worker.py`
- Predikciós logika: `app/predict.py`
- CMMS kliens: `app/cmms.py`
- Segédek (idempotencia hash, atomikus JSON írás): `app/utils.py`

## API végpontok (aktuális állapot)

### POST `/asset_predict`

- Input: `AssetPredictIn`
  - `operation_ids: list[int]`
  - `failure_start_time: datetime`
  - `maintenance_end_time: datetime`
  - `source_sys_time: datetime`
  - `asset_id: int`
  - `default_reliability: Optional[list[float]]`
- Kimenet: `AssetPredictOut` (`prediction_id: int`)
- Működés:
  - idempotencia hash készül a request body-ból (`request_sha256`)
  - ha van azonos hash-ű job, ugyanazt az azonosítót adja vissza
  - különben `prediction_jobs` rekord jön létre `endpoint_type="asset_predict"` értékkel

### POST `/asset_failure_type_predict`

- Input: `AssetFailureTypePredictIn`
  - mint fent, plusz `failure_type_ids: list[int]`
- Kimenet: `AssetFailureTypePredictOut` (`prediction_id: int`)
- Működés:
  - idempotens queue-olás
  - új job `endpoint_type="asset_failure_type_predict"`

### POST `/workrequest`

- Input: `AssetFailureTypePredictIn`
- Kimenet: `AssetFailureTypePredictOut` (`prediction_id: int`)
- Fontos: jelenlegi implementációban a létrehozott job nem kap `endpoint_type` értéket.
  - Az ORM szerint ez kötelező mező.
  - Emiatt ez a végpont jelen állapotában hibára futhat enqueue közben, és worker oldalon sincs külön `workrequest` feldolgozó ág.

## Folyamat áttekintés

1) API hívás érkezik.
2) FastAPI/Pydantic validálja a payloadot.
3) API idempotencia hash-t számol.
4) API meglévő jobot keres a hash alapján.
5) Ha nincs találat, új rekord jön létre a `prediction_jobs` táblában (`queued`).
6) A worker folyamatosan poll-ol, és `FOR UPDATE SKIP LOCKED` segítségével claim-eli a soron következő jobot.
7) A worker `processing` státuszra állít, majd lefuttatja a `process_job` logikát.
8) Kimenet:
  - DB insert a `prediction` táblába
  - JSON fájl a `DATA_DIR` könyvtárba
  - CMMS POST
9) Job státusz vége:
  - `done`
  - vagy `not_found`
  - vagy `error`

## Worker logika részletesen

## 1. Claim és retry/requeue

- `claim_one_job`:
  - kiválaszt egy `queued` sort
  - `processing` státuszra állítja
- `requeue_stuck_jobs`:
  - a túl sokáig `processing` státuszú jobokat visszateszi `queued`-ba
  - ha elérik a retry limitet, `error` állapotra vált

## 2. Payload újravalidálás

- `asset_predict` esetén `AssetPredictIn`
- `asset_failure_type_predict` esetén `AssetFailureTypePredictIn`
- validációs hiba esetén: `error`

## 3. Alapadatok biztosítása

- Asset ellenőrzés DB-ben, szükség esetén CMMS-ből betöltés (`cmms_get_assets`).
- Failure type ellenőrzés és CMMS fallback (`cmms_get_failure_types`) ott, ahol releváns.

## 4. `asset_failure_type_predict` specifikus előkészítés

- `failure_type_ids` nem lehet üres.
- CMMS-ből lekéri az `asset_failure_types` adatokat.
- `asset_id + failure_type_id -> asset_failure_type_id` leképezést épít.
- Upserteli az `asset_failure_type` táblát.
- A CMMS `asset_failure_types_operations` alapján ellenőrzi az operation típusokat (`BOTH`, `CORRECTIVE`, `PREVENTIVE`).

## 5. Operation és maintenance list ellenőrzés

- Minden `operation_id`-hoz biztosít egy helyi `operation` rekordot (idempotens insert).
- Ellenőrzi / betölti az operation-maintenance mappingokat
  - DB (`operations_maintenance_list`) vagy
  - CMMS (`cmms_get_operation_maintenance_lists`)

## 6. AML és AFT-AML relációk

- Biztosítja az `asset_maintenance_list` sorokat (`cmms_get_asset_maintenance_lists` fallback).
- `asset_failure_type_predict` esetén biztosítja az `asset_failure_type_asset_maintenance_list` relációkat.

## 7. Predikció és perzisztálás

- Horizont: `prediction_future_time = maintenance_end_time + 7 nap`.
- Predikció: `predict(...)`.
  - `asset_predict` esetben a jelenlegi implementáció 1.0 reliabilitást ad vissza.
  - `asset_failure_type_predict` esetben random valószínűségi eloszlást generál a megadott `failure_type_ids` listára.
- `predicted_reliability` clampelve van `0.0..0.99` közé.
- DB insert: `prediction` tábla.
- JSON mentés: `<DATA_DIR>/<prediction_id>.json`.
- CMMS POST:
  - `/asset_prediction` vagy
  - `/asset_failure_type_prediction`

## 8. Job lezárás

- Siker esetén: `done`, `prediction_id` kitöltve.
- CMMS hiba esetén: `error`, `prediction_id` megőrzésével.
- Hiányzó adat esetén: `not_found`.

## CMMS integráció (aktuális endpointok)

GET:

- `/assets?asset_id=...`
- `/failures?failure_id=...`
- `/failure_types/{failure_type_id}`
- `/maintenance_lists?maintenance_list_id=...`
- `/operation_maintenance_lists?operation_id=...`
- `/asset_failure_types` vagy `/asset_failure_types/{asset_id}`
- `/asset_failure_type_asset_maintenance_lists?asset_id=...&failure_type=...&default_reliability=...`
- `/asset_maintenance_lists?asset_id=...`
- `/asset_failure_types_operations?asset_id=...&failure_type_id=...`

POST:

- `/asset_prediction`
- `/asset_failure_type_prediction`
- `/workrequest`

Auth header:

- `x-api-key: <CMMS_TOKEN>`

## Idempotencia

- `request_sha256` determinisztikus JSON-t hash-el (`sort_keys=True`).
- datetime mezők ISO formátummal kerülnek hash-elésre.

## Ismert korlátok

- A dokumentációban korábban szereplő UUID típusok helyett a jelenlegi implementáció `int` ID-kat használ.
- `predict()` jelenleg nem használ `eta/beta` Weibull modellt a kimenethez.
- A `/workrequest` API útvonal jelenleg nincs végig implementálva a queue-worker láncban.

