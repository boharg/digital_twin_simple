import httpx
from .settings import settings


def _headers():
    return {"Authorization": f"Bearer {settings.CMMS_TOKEN}"}


async def cmms_get_asset(asset_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/assets"
    params = {"asset_id": asset_id}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching asset {asset_id}: {e}")
        return None


async def cmms_get_failures(failure_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/failures"
    params = {"failure_id": failure_id}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching failure {failure_id}: {e}")
        return None


async def cmms_get_failure_type(asset_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/failure_type"
    params = {"failure_type_id": asset_id}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching failure type {asset_id}: {e}")
        return None


async def cmms_get_maintenance_list(maintenance_list_id: str) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/maintenance_list"
    params = {"maintenance_list_id": maintenance_list_id}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching maintenance list {maintenance_list_id}: {e}")
        return None


async def cmms_get_operation_maintenance_lists(operation_id: str, maintenance_list_id: str | None = None) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/operation_maintenance_lists"
    params = {"operation_id": operation_id}
    try:
        if maintenance_list_id:
            params["maintenance_list_id"] = maintenance_list_id
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching operation maintenance lists for operation {operation_id}: {e}")
        return []


async def cmms_get_asset_failure_type_asset_maintenance_lists(asset_id: str, failure_type_id: str, default_reliability: int) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_asset_maintenance_lists"
    params = {"asset_id": asset_id, "failure_type": failure_type_id, "default_reliability": default_reliability}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching asset failure type asset maintenance lists for asset {asset_id} and failure type {failure_type_id}: {e}")
        return []


async def cmms_get_asset_maintenance_lists(asset_id: str) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_maintenance_lists"
    params = {"asset_id": asset_id}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers()) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        print(f"Error fetching asset maintenance lists for asset {asset_id}: {e}")
        return []


def cmms_post_asset_prediction_sync(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/asset_prediction"
    try:
        with httpx.Client(timeout=10.0, headers=_headers()) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}
    except httpx.HTTPError as e:
        print(f"Error posting asset prediction: {e}")
        return {"error": str(e)}


def cmms_post_asset_failure_type_prediction_sync(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_prediction"
    try:
        with httpx.Client(timeout=10.0, headers=_headers()) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}
    except httpx.HTTPError as e:
        print(f"Error posting asset failure type prediction: {e}")
        return {"error": str(e)}


def cmms_post_workrequest(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/workrequest"
    try:
        with httpx.Client(timeout=10.0, headers=_headers()) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}
    except httpx.HTTPError as e:
        print(f"Error posting workrequest: {e}")
        return {"error": str(e)}
