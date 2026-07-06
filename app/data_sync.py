from sqlalchemy import text, select
import time, os, asyncio
from sqlalchemy.orm import Session

from .models import (Asset,
                     FailureType,
                     MaintenanceList,
                     OperationsMaintenanceList,
                     AssetMaintenanceList
                     )
from .cmms import (cmms_get_assets,
                   cmms_get_maintenance_lists,
                   cmms_get_failure_types,
                   cmms_get_operation_maintenance_lists,
                   cmms_get_asset_maintenance_lists)


def _commit_before_cmms(session: Session):
    """
    Avoid holding open DB transactions while waiting on CMMS/network calls.
    """
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def ensure_asset(session: Session, asset_id: int) -> bool:
    asset = session.get(Asset, asset_id)
    if asset:
        # Close read-only transaction to avoid idle-in-transaction
        session.commit()
        return True
    # Ha nincs, megpróbáljuk CMMS-ből betölteni
    _commit_before_cmms(session)
    asset_json = asyncio.run(cmms_get_assets(asset_id))
    if not asset_json:
        return False
    if isinstance(asset_json, list):
        asset_json = next(
            (a for a in asset_json if int(a.get("asset_id", -1)) == int(asset_id)),
            None,
        )
        if not asset_json:
            return False
    session.merge(Asset(asset_id=asset_json["asset_id"],
                        asset_name=asset_json.get("asset_name", "")))
    session.commit()
    return True


def ensure_failure_type(session: Session, failure_type_id: int | None) -> bool:
    if failure_type_id is None:
        return False
    ft = session.get(FailureType, failure_type_id)
    if ft:
        # Close read-only transaction to avoid idle-in-transaction
        session.commit()
        return True
    _commit_before_cmms(session)
    ft_json = asyncio.run(cmms_get_failure_types(failure_type_id))
    if not ft_json:
        return False
    session.merge(FailureType(
        failure_type_id=ft_json["failure_type_id"],
        failure_type_name=ft_json.get("failure_type_name", "")
    ))
    session.commit()
    return True


def ensure_maintenance_list_row(session: Session, maintenance_list_id: int) -> bool:
    """
    Ensure a MaintenanceList row exists. If missing, try to fetch details from CMMS.
    """
    ml_id = maintenance_list_id
    ml = session.get(MaintenanceList, ml_id)
    if ml:
        # Close the read-only transaction to avoid idle-in-transaction
        session.commit()
        return True

    ml_json = None
    try:
        _commit_before_cmms(session)
        ml_json = asyncio.run(cmms_get_maintenance_lists(maintenance_list_id))
    except Exception:
        pass

    # CMMS may return a list; pick the matching item if so
    if isinstance(ml_json, list):
        ml_json = next(
            (r for r in ml_json if int(r.get("maintenance_list_id", -1)) == int(ml_id)),
            None,
        )

    session.add(MaintenanceList(
        maintenance_list_id=ml_id,
        maintenance_list_name=(ml_json or {}).get("maintenance_list_name", "")
    ))
    session.flush()
    return True


def ensure_operation_maintenance_lists(session: Session, operation_id: int) -> list[str]:
    # 1) Try DB mapping first
    op_id = operation_id
    db_ids = session.execute(
        select(OperationsMaintenanceList.maintenance_list_id)
        .where(OperationsMaintenanceList.operation_id == op_id)
    ).scalars().all()
    if db_ids:
        return [str(x) for x in db_ids]

    # 2) Fallback to CMMS
    rows = []
    try:
        _commit_before_cmms(session)
        rows = asyncio.run(cmms_get_operation_maintenance_lists(operation_id)) or []
    except Exception:
        rows = []

    ml_ids: list[str] = []
    for r in rows:
        ml_id = r.get("maintenance_list_id")
        if not ml_id:
            continue
        ml_ids.append(ml_id)
        # ensure maintenance_list row locally
        ensure_maintenance_list_row(session, ml_id)
        # ensure operation -> maintenance_list mapping (idempotent)
        session.execute(
            text("""
                INSERT INTO operations_maintenance_list (maintenance_list_id, operation_id)
                VALUES (:ml_id, :op_id)
                ON CONFLICT DO NOTHING
            """),
            {"ml_id": int(ml_id), "op_id": int(op_id)}
        )
    if ml_ids:
        session.flush()
    return ml_ids


def ensure_asset_maintenance_lists(session: Session, asset_id: int) -> list[str]:
    """
    Ensure maintenance_list mappings for the given asset.
    - If mappings exist locally, return them.
    - Else fetch from CMMS, upsert maintenance_list rows and asset_maintenance_list mappings.
    - If CMMS rows include operation_id, also upsert operations_maintenance_list.
    Returns the maintenance_list_ids mapped to the asset.
    """
    a_id = asset_id

    # 1) Local mappings
    db_ml_ids = session.execute(
        select(AssetMaintenanceList.maintenance_list_id)
        .where(AssetMaintenanceList.asset_id == a_id)
    ).scalars().all()
    if db_ml_ids:
        return [str(x) for x in db_ml_ids]

    # 2) Fallback to CMMS
    rows: list[dict] = []
    try:
        _commit_before_cmms(session)
        rows = asyncio.run(cmms_get_asset_maintenance_lists(asset_id)) or []
    except Exception:
        rows = []

    if not rows:
        return []

    for r in rows:
        ml_id = r.get("maintenance_list_id")
        if not ml_id:
            continue
        ml_id = int(ml_id)

        # Ensure maintenance_list row exists (pulls name if needed)
        ensure_maintenance_list_row(session, ml_id)

        # Ensure asset -> maintenance_list mapping
        exists_aml = session.execute(
            select(AssetMaintenanceList.asset_maintenance_list_id).where(
                AssetMaintenanceList.asset_id == a_id,
                AssetMaintenanceList.maintenance_list_id == ml_id
            ).limit(1)
        ).first()
        if not exists_aml:
            session.add(AssetMaintenanceList(asset_id=a_id, maintenance_list_id=ml_id))

        # Optionally ensure operation -> maintenance_list mapping if provided by CMMS
        op_id = r.get("operation_id")
        if op_id:
            op_uuid = int(op_id)
            exists_oml = session.execute(
                select(OperationsMaintenanceList.maintenance_list_id).where(
                    OperationsMaintenanceList.maintenance_list_id == ml_id,
                    OperationsMaintenanceList.operation_id == op_uuid
                ).limit(1)
            ).first()
            if not exists_oml:
                session.execute(
                    text("""
                        INSERT INTO operations_maintenance_list (maintenance_list_id, operation_id)
                        VALUES (:ml_id, :op_id)
                        ON CONFLICT DO NOTHING
                    """),
                    {"ml_id": int(ml_id), "op_id": int(op_uuid)}
                )

    session.flush()

    # Re-read and return
    db_ml_ids = session.execute(
        select(AssetMaintenanceList.maintenance_list_id)
        .where(AssetMaintenanceList.asset_id == a_id)
    ).scalars().all()
    return [str(x) for x in db_ml_ids]
