import httpx
from loguru import logger

from .settings import settings


def _headers() -> dict[str, str]:
    return {
        "x-api-key": settings.CMMS_TOKEN,
    }


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(10.0, connect=5.0, read=5.0)


def _log_start(method: str, url: str) -> None:
    logger.info("CMMS {} {}", method, url)


def _log_done(method: str, url: str, status_code: int, content_type: str | None = None) -> None:
    if content_type:
        logger.info("CMMS {} {} -> {} ({})", method, url, status_code, content_type)
    else:
        logger.info("CMMS {} {} -> {}", method, url, status_code)


def _json_or_status(
    response: httpx.Response,
) -> dict | list:
    content_type = response.headers.get(
        "content-type",
        "",
    )

    if "application/json" in content_type:
        return response.json()

    return {
        "status": response.status_code,
    }


async def cmms_get_asset_failure_causes(
    sf_asset_id: int,
) -> dict:
    url = (
        f"{settings.CMMS_BASE_URL}"
        f"/dt/asset_failure_causes/{sf_asset_id}"
    )

    try:
        _log_start(
            "GET",
            url,
        )

        async with httpx.AsyncClient(
            timeout=_timeout(),
            headers=_headers(),
        ) as client:
            response = await client.get(url)

        _log_done(
            "GET",
            url,
            response.status_code,
            response.headers.get("content-type"),
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(
                "Invalid asset_failure_causes response: "
                "the response must be a JSON object"
            )

        failure_causes = payload.get(
            "failure_causes",
        )

        if not isinstance(failure_causes, list):
            raise ValueError(
                "Invalid asset_failure_causes response: "
                "failure_causes must be a list"
            )

        response_asset_id = payload.get(
            "asset_id",
        )

        if (
            response_asset_id is not None
            and int(response_asset_id) != int(sf_asset_id)
        ):
            raise ValueError(
                "The asset_id returned by the CMMS "
                "does not match the requested sf_asset_id"
            )

        return payload

    except (httpx.HTTPError, ValueError) as error:
        logger.error(
            "Error fetching asset_failure_causes "
            "for sf_asset_id {}: {}",
            sf_asset_id,
            error,
        )
        raise


async def cmms_post_asset_prediction(
    payload: dict,
) -> dict | list:
    url = (
        f"{settings.CMMS_BASE_URL}"
        "/dt/asset_prediction"
    )

    try:
        _log_start(
            "POST",
            url,
        )

        async with httpx.AsyncClient(
            timeout=_timeout(),
            headers=_headers(),
        ) as client:
            response = await client.post(
                url,
                json=payload,
            )

        _log_done(
            "POST",
            url,
            response.status_code,
            response.headers.get("content-type"),
        )

        response.raise_for_status()

        return _json_or_status(response)

    except (httpx.HTTPError, ValueError) as error:
        logger.error(
            "Error posting asset prediction: {}",
            error,
        )
        raise


async def cmms_post_asset_failure_cause_prediction(
    payload: dict,
) -> dict | list:
    url = (
        f"{settings.CMMS_BASE_URL}"
        "/dt/asset_failure_cause_prediction"
    )

    try:
        _log_start(
            "POST",
            url,
        )

        async with httpx.AsyncClient(
            timeout=_timeout(),
            headers=_headers(),
        ) as client:
            response = await client.post(
                url,
                json=payload,
            )

        _log_done(
            "POST",
            url,
            response.status_code,
            response.headers.get("content-type"),
        )

        response.raise_for_status()

        return _json_or_status(response)

    except (httpx.HTTPError, ValueError) as error:
        logger.error(
            "Error posting asset failure cause "
            "prediction: {}",
            error,
        )
        raise