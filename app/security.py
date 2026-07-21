from hmac import compare_digest
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .maintenance.settings import settings


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


def require_api_key(
    provided_api_key: Annotated[str | None, Security(api_key_header)],
) -> None:
    """
    Ellenőrzi az X-API-Key fejlécben érkező API-kulcsot.

    Hiányzó vagy érvénytelen kulcs esetén 401 Unauthorized választ ad.
    """

    expected_api_key = settings.INBOUND_API_KEY.get_secret_value()

    if provided_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not compare_digest(provided_api_key, expected_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is invalid",
            headers={"WWW-Authenticate": "ApiKey"},
        )
