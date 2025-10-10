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


async def cmms_get_failures(failure_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/failures"
    params = {"failure_id": failure_id}
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


async def cmms_get_maintenance_list(maintenance_list_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/maintenance_list"
    params = {"maintenance_list_id": maintenance_list_id}
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def cmms_get_operation_maintenance_lists(operation_id: str, maintenance_list_id: str | None = None) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/operation_maintenance_lists"
    params = {"operation_id": operation_id}
    if maintenance_list_id:
        params["maintenance_list_id"] = maintenance_list_id
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def cmms_get_asset_failure_type_asset_maintenance_lists(asset_id: str, failure_type_id: str, default_reliability: int) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_asset_maintenance_lists"
    params = {"asset_id": asset_id, "failure_type": failure_type_id, "default_reliability": default_reliability}
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def cmms_get_asset_maintenance_lists(asset_id: str) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_maintenance_lists"
    params = {"asset_id": asset_id}
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def cmms_get_asset_failure_type_asset_maintenance_lists(asset_failure_type_id: str) -> list[dict]:
    # expects: { "asset_failure_type_asset_maintenance_list_id": "...",
    #            "asset_maintenance_list_id": "...", "default_reliability": 0.95 }
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_asset_maintenance_lists"
    params = {"asset_failure_type_id": asset_failure_type_id}
    async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
        r = await client.get(url, params=params)
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
