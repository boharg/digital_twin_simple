# digital_twin_simple - for predicting reliability
## Főbb jellemzők
Folyamatos fogadás: az API csak sorba állít (DB-be ír), azonnal UUID/202 választ ad. A hosszabb algoritmusok a workerben futnak, így közben jöhetnek új API hívások.

Tartós queue: a prediction_jobs tábla maga a queue, amit feldolgozunk. Crash után a queued rekordok megmaradnak.

Konkurrencia: több worker is futhat; FOR UPDATE SKIP LOCKED gondoskodik róla, hogy egy rekordot egyszerre csak egy worker vigyen.

Meglévő db sémákat használat: asset, failure_type, asset_failure_type, sensor, sensor_failure_type, gamma, eta_beta, prediction – ezekre nem futtatunk create_all-t; csak olvasunk/írunk beléjük - ki kell egészíteni majd a többi táblával.

Asset pótolható CMMS-ből: ha hiányzik az asset, az API nem áll le – a worker megpróbálja a CMMS-ből pótolni, és INSERT az asset táblába - ze tis bővíteni kell a többi adatra és CMMS endpointra

Ellenőrzés a timescale idősoros adaton: gamma → sensor_failure_type → sensor (asset) join, time BETWEEN - ehelyett majd lehet másikat haználni, ha András mást választ

Predikció: ha van eta_beta, Weibull; ha nincs, default_reliability átlag vagy 0.9 fallback - ez is módosulhat András megoldásától függően

Eredmény perzisztencia: prediction tábla insert + JSON fájl + CMMS POST.

# Python környezet:

python -m venv .venv

## Windows 

.venv\Scripts\activate.bat

## Ubuntu

source .venv/bin/activate

## Csomagok telepítése

pip install --upgrade pip

pip install -r requirements.txt

# Környezeti változók (pl. .env – lásd settings.py):

DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/appdb

ASYNC_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/appdb
CMMS_BASE_URL=https://cmms.example.com/api

CMMS_TOKEN=replace-me

DATA_DIR=./prediction_out

# Indítás:

## API (8000-es porton)

uvicorn app.main:app --reload

## Worker külön terminálban

python -m app.worker
