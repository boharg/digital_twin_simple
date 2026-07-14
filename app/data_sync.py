import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .maintenance.cmms import cmms_get_asset_failure_causes
from .models import Asset, AssetFailureType, FailureType


def _commit_before_cmms(session: Session):
    """
    Avoid holding open DB transactions while waiting on CMMS/network calls.
    """
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def _as_list_payload(data: Any, key: str) -> list[dict]:
    if not data:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        rows = data.get(key)
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def _first_present(row: dict, *keys: str):
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def ensure_asset(session: Session, asset_id: int) -> bool:
    """
    Check whether the CMMS-provided asset_id already exists locally.
    """
    if asset_id is None:
        return False

    asset_id = int(asset_id)
    asset = session.get(Asset, asset_id)
    session.commit()
    return asset is not None


def ensure_failure_type(
    session: Session,
    failure_cause_id: int | None,
    failure_type_name: str | None = None,
    is_preventive: bool | None = None,
) -> bool:
    """
    The local failure_type_id stores the same value as the CMMS
    failure_cause_id. A missing failure_cause_id means planned maintenance, so
    no failure_type row is required.
    """
    if failure_cause_id is None:
        return True

    failure_cause_id = int(failure_cause_id)
    ft = session.get(FailureType, failure_cause_id)
    if ft:
        if failure_type_name is not None:
            ft.failure_type_name = failure_type_name
        if is_preventive is not None:
            ft.is_preventive = True
        if ft.failure_cause_id is None:
            ft.failure_cause_id = failure_cause_id
        session.commit()
        return True

    session.add(
        FailureType(
            failure_type_id=failure_cause_id,
            failure_type_name=failure_type_name,
            is_preventive=is_preventive,
            failure_cause_id=failure_cause_id,
        )
    )
    session.commit()
    return True


def ensure_asset_failure_types(session: Session, asset_id: int) -> list[int]:
    """
    Load CMMS asset failure causes into local asset_failure_types.
    """
    asset_id = int(asset_id)
    if not ensure_asset(session, asset_id):
        return []

    existing_ids = session.execute(
        select(AssetFailureType.asset_failure_type_id).where(
            AssetFailureType.asset_id == asset_id
        )
    ).scalars().all()

    _commit_before_cmms(session)
    payload = asyncio.run(cmms_get_asset_failure_causes(asset_id))
    rows = _as_list_payload(payload, "failure_causes")
    if not rows:
        return [int(item) for item in existing_ids]

    synced_ids: list[int] = []
    for row in rows:
        asset_failurecause_id = _first_present(
            row,
            "asset_failurecause_id",
            "asset_failure_cause_id",
            "asset_failure_casue_id",
        )
        failure_cause_id = row.get("failure_cause_id")

        if asset_failurecause_id is None and failure_cause_id is None:
            continue

        failure_type_name = _first_present(row, "failure_type_name", "failure_cause_name", "code")
        ensure_failure_type(
            session,
            int(failure_cause_id) if failure_cause_id is not None else None,
            failure_type_name=str(failure_type_name) if failure_type_name is not None else None,
        )

        query = select(AssetFailureType).where(AssetFailureType.asset_id == asset_id)
        if asset_failurecause_id is not None:
            query = query.where(
                AssetFailureType.asset_failurecause_id == int(asset_failurecause_id)
            )
        elif failure_cause_id is not None:
            query = query.where(AssetFailureType.failure_type_id == int(failure_cause_id))

        aft = session.execute(query).scalar_one_or_none()

        if aft is None:
            aft = AssetFailureType(
                asset_id=asset_id,
                failure_type_id=int(failure_cause_id) if failure_cause_id is not None else None,
                asset_failurecause_id=(
                    int(asset_failurecause_id) if asset_failurecause_id is not None else None
                ),
            )
            session.add(aft)
        elif failure_cause_id is not None:
            aft.failure_type_id = int(failure_cause_id)
        if asset_failurecause_id is not None:
            aft.asset_failurecause_id = int(asset_failurecause_id)

        probability = row.get("default_occurence_probability")
        if probability is None:
            probability = row.get("default_occurrence_probability")
        aft.default_occurence_probability = probability

        severity = row.get("severity")
        aft.severity = int(severity) if severity is not None else None

        session.flush()
        if aft.asset_failure_type_id is not None:
            synced_ids.append(int(aft.asset_failure_type_id))

    session.commit()
    return synced_ids


def resolve_asset_failure_type_id(
    session: Session,
    asset_id: int,
    failure_cause_id: int | None,
) -> int | None:
    """
    Return the local asset_failure_type_id for an incoming CMMS failure_cause_id.

    Planned maintenance can arrive with failure_cause_id=None. In that case
    there is no failure-specific asset_failure_type to resolve.
    """
    if failure_cause_id is None:
        return None

    aft_id = session.execute(
        select(AssetFailureType.asset_failure_type_id).where(
            AssetFailureType.asset_id == int(asset_id),
            AssetFailureType.failure_type_id == int(failure_cause_id),
        )
    ).scalar_one_or_none()

    return int(aft_id) if aft_id is not None else None
