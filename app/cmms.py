import httpx
from loguru import logger
from .settings import settings


def _headers():
    return {"x-api-key": settings.CMMS_TOKEN}


def _timeout():
    # Hard timeouts to avoid hanging workers
    return httpx.Timeout(10.0, connect=5.0, read=5.0)


def _log_start(method: str, url: str, params: dict | None = None):
    logger.info("CMMS {} {} params={}", method, url, params or {})


def _log_done(method: str, url: str, status_code: int, content_type: str | None = None):
    if content_type:
        logger.info("CMMS {} {} -> {} ({})", method, url, status_code, content_type)
    else:
        logger.info("CMMS {} {} -> {}", method, url, status_code)


async def cmms_get_assets(asset_id: int) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/assets"
    params = {"asset_id": asset_id}
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching asset {}: {}", asset_id, e)
        return None


async def cmms_get_failures(failure_id: int) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/failures"
    params = {"failure_id": failure_id}
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching failure {}: {}", failure_id, e)
        return None


async def cmms_get_failure_types(failure_type_id: int) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/failure_types/{failure_type_id}"
    try:
        _log_start("GET", url)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url)
            if r.status_code == 404:
                return None
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching failure type {}: {}", failure_type_id, e)
        return None


async def cmms_get_maintenance_lists(maintenance_list_id: int) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/maintenance_lists"
    params = {"maintenance_list_id": maintenance_list_id}
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return None
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "application/json" not in ct:
                logger.warning("maintenance_list non-JSON response: {}", ct)
                return None
            return r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.error("Error fetching maintenance list {}: {}", maintenance_list_id, e)
        return None


async def cmms_get_operation_maintenance_lists(operation_id: int, maintenance_list_id: int | None = None) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/operation_maintenance_lists"
    params = {"operation_id": operation_id}
    try:
        if maintenance_list_id:
            params["maintenance_list_id"] = maintenance_list_id
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching operation maintenance lists for operation {}: {}", operation_id, e)
        return []


async def cmms_get_asset_failure_types(asset_id: int | None = None) -> list[dict]:
    if asset_id is None:
        url = f"{settings.CMMS_BASE_URL}/asset_failure_types"
        params = {}
    else:
        url = f"{settings.CMMS_BASE_URL}/asset_failure_types/{asset_id}"
        params = {}
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching asset_failure_types for asset {}: {}", asset_id, e)
        return []


async def cmms_get_asset_failure_type_asset_maintenance_lists(asset_id: int, failure_type_id: int, default_reliability: float) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_asset_maintenance_lists"
    params = {"asset_id": asset_id, "failure_type": failure_type_id, "default_reliability": default_reliability}
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching asset failure type asset maintenance lists for asset {} and failure type {}: {}", asset_id, failure_type_id, e)
        return []


async def cmms_get_asset_maintenance_lists(asset_id: int) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_maintenance_lists"
    params = {"asset_id": asset_id}
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching asset maintenance lists for asset {}: {}", asset_id, e)
        return []


async def cmms_post_asset_prediction_sync(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/asset_prediction"
    try:
        _log_start("POST", url)
        with httpx.Client(timeout=_timeout(), headers=_headers()) as client:
            r = client.post(url, json=payload)
            _log_done("POST", url, r.status_code, r.headers.get("content-type"))
            if r.status_code >= 400:
                return {
                    "error": f"HTTP {r.status_code}",
                    "body": r.text,
                }
            return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}
    except httpx.HTTPError as e:
        logger.error("Error posting asset prediction: {}", e)
        return {"error": str(e)}


async def cmms_post_asset_failure_type_prediction_sync(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/asset_failure_type_prediction"
    try:
        _log_start("POST", url)
        with httpx.Client(timeout=_timeout(), headers=_headers()) as client:
            r = client.post(url, json=payload)
            _log_done("POST", url, r.status_code, r.headers.get("content-type"))
            if r.status_code >= 400:
                return {
                    "error": f"HTTP {r.status_code}",
                    "body": r.text,
                }
            return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}
    except httpx.HTTPError as e:
        logger.error("Error posting asset failure type prediction: {}", e)
        return {"error": str(e)}


async def cmms_post_workrequest(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/workrequest"
    try:
        _log_start("POST", url)
        with httpx.Client(timeout=_timeout(), headers=_headers()) as client:
            r = client.post(url, json=payload)
            _log_done("POST", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json() if "application/json" in r.headers.get("content-type", "") else {"status": r.status_code}
    except httpx.HTTPError as e:
        logger.error("Error posting workrequest: {}", e)
        return {"error": str(e)}


async def cmms_get_asset_failure_type_operations(
    asset_id: int | None = None,
    failure_type_id: int | None = None,
) -> list[dict]:
    url = f"{settings.CMMS_BASE_URL}/asset_failure_types_operations"
    params = {}
    if asset_id is not None:
        params["asset_id"] = asset_id
    if failure_type_id is not None:
        params["failure_type_id"] = failure_type_id
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("Error fetching asset_failure_type_operations: {}", e)
        return []
