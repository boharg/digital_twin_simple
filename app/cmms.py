import httpx
from .settings import settings


def _headers():
    return {"Authorization": f"Bearer {settings.CMMS_TOKEN}"}


async def cmms_get_asset(asset_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/assets"
    params = {"asset_id": asset_id}
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def cmms_get_failure_type(asset_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/failure_type"
    params = {"failure_type_id": asset_id}
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def cmms_post_asset_prediction_sync(payload: dict):
    import httpx
    url = f"{settings.CMMS_BASE_URL}/asset_prediction"
    with httpx.Client(timeout=10.0, headers=_headers()) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}


def cmms_post_asset_failure_type_prediction_sync(payload: dict):
    import httpx
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_predict"
    with httpx.Client(timeout=10.0, headers=_headers()) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}


def cmms_post_workrequest(payload: dict):
    import httpx
    url = f"{settings.CMMS_BASE_URL}/workrequest"
    with httpx.Client(timeout=10.0, headers=_headers()) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}


