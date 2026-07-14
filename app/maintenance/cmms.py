import httpx
from loguru import logger
from .settings import settings


def _headers():
    return {"x-api-key": settings.CMMS_TOKEN}


def _timeout():
    return httpx.Timeout(10.0, connect=5.0, read=5.0)


def _log_start(method: str, url: str, params: dict | None = None):
    logger.info("CMMS {} {} params={}", method, url, params or {})


def _log_done(method: str, url: str, status_code: int, content_type: str | None = None):
    if content_type:
        logger.info("CMMS {} {} -> {} ({})", method, url, status_code, content_type)
    else:
        logger.info("CMMS {} {} -> {}", method, url, status_code)


def _json_or_status(response: httpx.Response) -> dict | list | None:
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return {"status": response.status_code}


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


async def cmms_get_asset_failure_causes(asset_id: int) -> dict:
    url = f"{settings.CMMS_BASE_URL}/dt/asset_failure_causes/{asset_id}"
    try:
        _log_start("GET", url)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            data = _json_or_status(r)
            return data if isinstance(data, dict) else {"asset_id": asset_id, "failure_causes": data or []}
    except httpx.HTTPError as e:
        logger.error("Error fetching asset_failure_causes for asset {}: {}", asset_id, e)
        return {"asset_id": asset_id, "failure_causes": []}


async def cmms_get_workorders(
    asset_id: int,
    page: int = 1,
    limit: int = 20,
    from_date: str | None = None,
    type: str | None = None,
) -> dict:
    url = f"{settings.CMMS_BASE_URL}/dt/workorders/{asset_id}"
    params: dict[str, int | str] = {"page": page, "limit": limit}
    if from_date is not None:
        params["from_date"] = from_date
    if type is not None:
        params["type"] = type
    try:
        _log_start("GET", url, params)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url, params=params)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            data = _json_or_status(r)
            return data if isinstance(data, dict) else {"asset_id": asset_id, "workorders": data or []}
    except httpx.HTTPError as e:
        logger.error("Error fetching workorders for asset {}: {}", asset_id, e)
        return {"asset_id": asset_id, "workorders": []}


async def cmms_post_asset_prediction_sync(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/dt/asset_prediction"
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
            return _json_or_status(r)
    except httpx.HTTPError as e:
        logger.error("Error posting asset prediction: {}", e)
        return {"error": str(e)}


async def cmms_post_asset_failure_cause_prediction(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/dt/asset_failure_cause_prediction"
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
            return _json_or_status(r)
    except httpx.HTTPError as e:
        logger.error("Error posting asset failure cause prediction: {}", e)
        return {"error": str(e)}


async def cmms_post_workrequest(payload: dict):
    url = f"{settings.CMMS_BASE_URL}/workrequest"
    try:
        _log_start("POST", url)
        with httpx.Client(timeout=_timeout(), headers=_headers()) as client:
            r = client.post(url, json=payload)
            _log_done("POST", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            return _json_or_status(r)
    except httpx.HTTPError as e:
        logger.error("Error posting workrequest: {}", e)
        return {"error": str(e)}


async def cmms_get_asset_failure_cause(asset_id: int, failure_cause_id: int) -> dict | None:
    url = f"{settings.CMMS_BASE_URL}/dt/asset_failure_causes/{asset_id}/{failure_cause_id}"
    try:
        _log_start("GET", url)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url)
            if r.status_code == 404:
                return None
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            data = _json_or_status(r)
            return data if isinstance(data, dict) else None
    except httpx.HTTPError as e:
        logger.error(
            "Error fetching asset_failure_cause for asset {} and failure_cause {}: {}",
            asset_id,
            failure_cause_id,
            e,
        )
        return None


async def cmms_get_asset_failure_causes_operation(asset_id: int, operation_id: int) -> dict:
    url = f"{settings.CMMS_BASE_URL}/dt/asset_failure_causes/{asset_id}/{operation_id}"
    try:
        _log_start("GET", url)
        async with httpx.AsyncClient(timeout=_timeout(), headers=_headers()) as client:
            r = await client.get(url)
            _log_done("GET", url, r.status_code, r.headers.get("content-type"))
            r.raise_for_status()
            data = _json_or_status(r)
            return data if isinstance(data, dict) else {
                "asset_id": asset_id,
                "operation_id": operation_id,
                "failure_causes": data or [],
            }
    except httpx.HTTPError as e:
        logger.error(
            "Error fetching asset_failure_causes_operation for asset {} and operation {}: {}",
            asset_id,
            operation_id,
            e,
        )
        return {"asset_id": asset_id, "operation_id": operation_id, "failure_causes": []}