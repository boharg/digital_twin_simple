# digital_twin_simple – Működési dokumentáció (hívási sorrend, adatáramlás)

Ez a dokumentum a futás közbeni működésre fókuszál: mely végpont mit csinál, milyen sorrendben mely függvények hívódnak, és milyen adatokat adnak át egymásnak.

## Fő komponensek

- API (FastAPI, aszinkron): `app/main.py:15`
- Adatsémák (Pydantic): `app/schemas.py:7`, `app/schemas.py:22`
- DB kapcsolatok: aszinkron API-hoz és szinkron workerhez `app/db.py:7`, `app/db.py:16`
- ORM modellek és queue tábla: `app/models.py:23` (`PredictionJob`), további táblák `app/models.py:43`-
- Worker (DB-queue feldolgozó): `app/worker.py:550`
- Predikciós logika: `app/predict.py:13`, `app/predict.py:35`
- CMMS kliens hívások (HTTP): `app/cmms.py`
- Kiegészítők: idempotencia hash, atomikus JSON-mentés: `app/utils.py:7`, `app/utils.py:28`

## Folyamat áttekintés

1) Bejövő API hívás (`POST /asset_predict` vagy `POST /asset_failure_type_predict`):
   - Pydantic validálás és idempotencia hash (`request_sha256`) – `app/main.py:28`–`app/main.py:46`, `app/utils.py:7`.
   - Queue rekord létrehozása a `prediction_jobs` táblában (`status=queued`, `endpoint_type=...`) – `app/main.py:41`–`app/main.py:46`, `app/models.py:23`.
   - Azonnali válasz 202 és egy `prediction_id`-ként szolgáló UUID (valójában a `job_id`, amíg nincs végleges predikció) – `app/main.py:46`.

2) Worker ciklus (folyamatosan poll-ol a DB-queue-ra):
   - Rekord „claimelése” `FOR UPDATE SKIP LOCKED`-dal → `status=processing` – `app/worker.py:46`–`app/worker.py:63`.
   - Feldolgozás: bemeneti payload validálás, adatok előkészítése, predikció, perzisztálás, CMMS POST – `app/worker.py:383`–`app/worker.py:547`.
   - Siker esetén `status=done` és `prediction_id` beírása a job-hoz – `app/worker.py:544`–`app/worker.py:547`.

3) Eredmények:
   - JSON fájl a `settings.DATA_DIR` mappában – `app/worker.py:475`–`app/worker.py:477`, `app/settings.py:12`, `app/utils.py:28`.
   - Sor `prediction` táblában – `app/worker.py:479`–`app/worker.py:487`, `app/models.py:105`.
   - CMMS-nek szinkron HTTP POST – `app/worker.py:489`–`app/worker.py:501` (asset), `app/worker.py:531`–`app/worker.py:542` (asset_failure_type).

## Végpontok és hívási sorrend

### POST `/asset_predict`

- Definíció: `app/main.py:28`
- Bemenet (Pydantic): `AssetPredictIn` – `app/schemas.py:7`
  - `operation_id: list[UUID]`
  - `failure_start_time: datetime`
  - `maintenance_end_time: datetime`
  - `source_sys_time: datetime`
  - `asset_id: UUID`
  - `failure_type_id: Optional[UUID]` (megj.: a worker jelenleg elvárja) 
  - `default_reliability: Optional[list[float]]`
- Lépések az API-ban: 
  - `request_sha256(body.model_dump())` → `req_hash` – `app/main.py:31`–`app/main.py:33`, `app/utils.py:7`.
  - Idempotencia: SELECT by `request_hash` a `prediction_jobs`-ban – `app/main.py:35`–`app/main.py:40`.
  - Ha nincs meglévő rekord: `PredictionJob(request_hash=req_hash, payload=payload, status=queued, endpoint_type="asset_predict")` → INSERT → 202 válasz `prediction_id=job.job_id` – `app/main.py:41`–`app/main.py:46`.

Worker feldolgozás (részletesen lejjebb): `endpoint_type == "asset_predict"` ágon predikál és CMMS `asset_prediction`-t hív – `app/worker.py:459`–`app/worker.py:501`.

### POST `/asset_failure_type_predict`

- Definíció: `app/main.py:49`
- Bemenet: `AssetFailureTypePredictIn` – `app/schemas.py:22`
  - Mint fent, de `failure_type_id: UUID` kötelező.
- API lépések megegyeznek az `asset_predict`-tel, `endpoint_type="asset_failure_type_predict"` – `app/main.py:59`.
- Worker a megfelelő ágon predikál és CMMS `asset_failure_type_prediction`-t hív – `app/worker.py:501`–`app/worker.py:542`.

### GET `/asset`

- Definíció: `app/main.py:83`
- Cél: asset lekérdezése DB-ből, ha nincs, „Unknown” névvel tér vissza. (Megjegyzés: a kód jelenleg `select(Base)`-t használ, ami vélhetően javításra szorul az `Asset` modellre.) – `app/main.py:85`–`app/main.py:91`.

### GET `/maintenance_lists`

- Definíció: `app/main.py:93`
- Cél: maintenance lista lekérdezése DB-ből, ha nincs, „Unknown” névvel tér vissza. (Megjegyzés: itt is `select(Base)` szerepel, várhatóan `MaintenanceList`-re kell cserélni.) – `app/main.py:95`–`app/main.py:100`.

## Worker – részletes lépések és hívások

Belépés és ciklus:

- `main()` → végtelen ciklus, minden iterációban `session_scope()` – `app/worker.py:550`–`app/worker.py:563`.
- `session_scope()` contextmanager biztosítja a commit/rollback/close-t – `app/worker.py:33`–`app/worker.py:43`.
- `claim_one_job(session)` kiválaszt egy `queued` rekordot SKIP LOCKED-dal, `status=processing` – `app/worker.py:46`–`app/worker.py:63`.
- `process_job(session, job)` végzi a tényleges feldolgozást – `app/worker.py:383`.

process_job fő lépések és függvényhívások:

1) Payload validálás: `p = AssetPredictIn(**job.payload)` – `app/worker.py:383`–`app/worker.py:391`.

2) Mezők feloldása:
   - `asset_id = str(p.asset_id)` – `app/worker.py:393`.
   - `start = p.failure_start_time`, `end = p.maintenance_end_time`, `source_time = p.source_sys_time` – `app/worker.py:394`–`app/worker.py:396`.
   - `failure_type_id = str(p.failure_type_id)` – `app/worker.py:397`.
   - `operation_ids = [str(...)]` – `app/worker.py:398`–`app/worker.py:399`.

3) Alap adatok biztosítása:
   - `ensure_asset(session, asset_id)` → ha nincs DB-ben, CMMS-ből lekéri (`cmms_get_asset`) és `Asset`-et `merge`-li – `app/worker.py:84`–`app/worker.py:95` (hív CMMS: `app/cmms.py:9`).
   - `ensure_failure_type(session, failure_type_id)` → ha nincs DB-ben, CMMS-ből lekéri (`cmms_get_failure_type`) és `FailureType`-ot `merge`-li – `app/worker.py:98`–`app/worker.py:112` (hív CMMS: `app/cmms.py:39`).

4) Kapcsolódó adatok ellenőrzése:
   - Opcionális timescale/gamma ellenőrzés (jelenleg kikommentezve) – `app/worker.py:414`–`app/worker.py:419`, lekérdező: `has_gamma_data()` `app/worker.py:128`–`app/worker.py:150`.
   - Műveletekhez (`operation_id`) tartozó maintenance lista megléte: 
     - `has_maintenanace_list(session, op_id)` vagy 
     - `ensure_operation_maintenanace_lists(session, op_id)` → ha DB-ben nincs, CMMS-ből betölti és feltölti a mappingeket – `app/worker.py:421`–`app/worker.py:429`, `app/worker.py:190`–`app/worker.py:222` (CMMS: `app/cmms.py:69`).

5) Kulcsazonosítók feloldása és kapcsolatok biztosítása:
   - `aft_id = ensure_asset_failure_type_id(session, asset_id, failure_type_id)` – `app/worker.py:431`–`app/worker.py:437`, feloldó: `app/worker.py:312`–`app/worker.py:325`.
   - `ensure_asset_maintenance_lists(session, asset_id)` → ha nincs mapping, CMMS-ből tölti fel és felveszi az `asset_maintenance_list` sorokat – `app/worker.py:439`–`app/worker.py:445`, részletek: `app/worker.py:225`–`app/worker.py:295` (CMMS: `app/cmms.py:97`).
   - `ensure_asset_maintenance_lists_asset_failure_type(session, asset_id, failure_type_id)` → hiányzó AFT↔AML mappingek felvétele (default_reliability=1), visszaadott ML ID-k – `app/worker.py:446`–`app/worker.py:451`, részletek: `app/worker.py:328`–`app/worker.py:380`.

6) Predikciós horizont:
   - `prediction_future_time = compute_prediction_future_time(end, days_ahead=7)` – `app/worker.py:456`–`app/worker.py:457`, `app/predict.py:35`.

7) Predikció és kimenetek (áganként):
   - Közös predikcióhívás: `predict_reliability(...)` – `app/worker.py:461`–`app/worker.py:469`, `app/worker.py:503`–`app/worker.py:511`, implementáció: `app/predict.py:13`.
   - `pred_id = uuid.uuid4()` és kimeneti JSON: `{ "prediction_id": str(pred_id), "predicted_reliability": float(value) }` – `app/worker.py:472`–`app/worker.py:477`, `app/utils.py:28`.
   - DB insert a `prediction` táblába: `insert_prediction_row(...)` – `app/worker.py:479`–`app/worker.py:487`, beszúrás: `app/worker.py:66`–`app/worker.py:81`.
   - CMMS POST:
     - Asset szint: `cmms_post_asset_prediction_sync(out)` – `app/worker.py:489`–`app/worker.py:501`, endpoint: `app/cmms.py:110`.
     - Asset-failure-type szint: `cmms_post_asset_failure_type_prediction_sync(out)` – `app/worker.py:531`–`app/worker.py:542`, endpoint: `app/cmms.py:122`.

8) Állapot frissítés a job-on: `job.status = done`, `job.prediction_id = pred_id` – `app/worker.py:544`–`app/worker.py:547`.

## Adatmodellek és adattáblák (röviden)

- Queue tábla: `PredictionJob` – `app/models.py:23`
  - Mezők: `job_id`, `request_hash`, `payload` (JSON), `status` (`queued|processing|done|not_found|error`), `endpoint_type`, `prediction_id`, `error_message`, `created_at`, `updated_at`.
- Domain táblák: `Asset`, `FailureType`, `AssetFailureType`, `Sensor`, `SensorFailureType`, `Gamma`, `EtaBeta`, `Prediction`, `MaintenanceList`, `OperationsMaintenanceList`, `AssetMaintenanceList`, `AssetFailureTypeAssetMaintenanceList` – `app/models.py:43`–

## Külső CMMS hívások

- GET-ek (aszinkron):
  - `cmms_get_asset(asset_id)` – `app/cmms.py:9`
  - `cmms_get_failure_type(failure_type_id)` – `app/cmms.py:39`
  - `cmms_get_maintenance_list(maintenance_list_id)` – `app/cmms.py:54`
  - `cmms_get_operation_maintenance_lists(operation_id, maintenance_list_id?)` – `app/cmms.py:69`
  - `cmms_get_asset_maintenance_lists(asset_id)` – `app/cmms.py:97`
- POST-ok (szinkron):
  - `cmms_post_asset_prediction_sync(payload)` – `app/cmms.py:110`
  - `cmms_post_asset_failure_type_prediction_sync(payload)` – `app/cmms.py:122`
  - `cmms_post_workrequest(payload)` – `app/cmms.py:134`

Mindegyik `Authorization: Bearer <CMMS_TOKEN>` fejléccel dolgozik – `app/cmms.py:5`–`app/cmms.py:6`. Alap URL: `settings.CMMS_BASE_URL` – `app/settings.py:10`.

## Idempotencia és JSON mentés

- Idempotencia hash: `request_sha256(payload)` – `app/utils.py:7`.
  - Dátumok ISO-8601 formátumban, UUID-k stringgé alakítva, determinisztikus JSON szortírozással.
- Atomikus JSON mentés: `atomic_write_json(path, data)` – `app/utils.py:28`.

## Hibakezelés és státuszok

- Worker `process_job` közben a következő jogi kimenetek lehetnek:
  - `error`: payload validációs hiba, vagy CMMS POST hiba – `app/worker.py:387`–`app/worker.py:391`, `app/worker.py:495`–`app/worker.py:501`, `app/worker.py:537`–`app/worker.py:542`.
  - `not_found`: hiányzó alap/kapcsolati adatok (asset, failure_type, mappingek, stb.) – `app/worker.py:401`–`app/worker.py:451`.
  - `done`: predikció sikeres, `prediction_id` kitöltve – `app/worker.py:544`–`app/worker.py:547`.

## Megjegyzések / inkonzisztenciák

- `asset_predict` séma megjegyzése szerint `failure_type_id` opcionális (`app/schemas.py:14`), azonban a worker jelenlegi implementációja megköveteli és `not_found`-dal visszatér, ha hiányzik (`app/worker.py:408`–`app/worker.py:412`). Érdemes az elvárást egyeztetni és a kódot/sémát összhangba hozni.
- Az API `GET /asset` és `GET /maintenance_lists` végpontjai `select(Base)`-et használnak a konkrét modellek helyett (`app/main.py:85`, `app/main.py:96`). Ez valószínűleg `Asset`/`MaintenanceList`-re javítandó.
- A Weibull alapú predikció jelenleg kikommentezve van (nincs `eta/beta` betöltés), emiatt a `predict_reliability` a `default_reliability` vagy 0.9 alapértékre esik vissza – `app/worker.py:466`–`app/worker.py:469`, `app/predict.py:31`.

## Indítási jegyzetek (röviden)

- API: `uvicorn app.main:app --reload` – lásd `README.md`.
- Worker: `python -m app.worker`.
- Környezet: `DATABASE_URL`, `ASYNC_DATABASE_URL`, `CMMS_BASE_URL`, `CMMS_TOKEN`, `DATA_DIR` – `app/settings.py:7`–`app/settings.py:14`.

