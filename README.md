# digital_twin_simple - for predicting reliability
## Főbb jellemzők
Folyamatos fogadás: az API csak sorba állít (DB-be ír), azonnal UUID/202 választ ad. A hosszabb algoritmusok a workerben futnak, így közben jöhetnek új API hívások.

Tartós queue: a prediction_jobs tábla maga a queue, amit feldolgozunk. Crash után a queued rekordok megmaradnak.

Konkurrencia: több worker is futhat; FOR UPDATE SKIP LOCKED gondoskodik róla, hogy egy rekordot egyszerre csak egy worker vigyen.

Eredmény perzisztencia: prediction tábla insert + JSON fájl + CMMS POST.

# Indítás:

## API (8000-es porton)

uvicorn app.main:app --reload

## Worker külön terminálban

python -m app.worker

