import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .maintenance.cmms import (
    cmms_get_asset_failure_causes,
)
from .models import (
    Asset,
    AssetFailureType,
    AssetWorksheetList,
    FailureType,
    OperationsDoneList,
)
from .schemas import AssetPredictIn


class DataSyncNotFoundError(Exception):
    """
    A szükséges külső vagy helyi adat nem található.
    """


class DataSyncValidationError(Exception):
    """
    A kapott adatok szerkezete vagy kapcsolata hibás.
    """


@dataclass(frozen=True)
class WorkorderSyncResult:
    """
    A munkalap-szinkronizálás eredménye.

    Az asset_id a saját rendszer belső azonosítója.

    A failure_cause_operations dictionary alakja:

        {
            asset_failurecause_id: [
                operation_id,
                ...
            ]
        }
    """

    asset_id: int
    asset_failure_type_id: int | None
    asset_worksheet_list_id: int
    maintenance_end_date: datetime
    failure_cause_operations: dict[int, list[int]]


def resolve_asset_id(
    session: Session,
    sf_asset_id: int,
) -> int:
    """
    A SilverFrogtól érkező külső assetazonosító
    alapján visszaadja a saját rendszerben generált
    belső asset_id értéket.

    Külső azonosító:
        assets.sf_asset_id

    Belső azonosító:
        assets.asset_id
    """
    asset_id = session.execute(
        select(Asset.asset_id).where(
            Asset.sf_asset_id == int(sf_asset_id)
        )
    ).scalar_one_or_none()

    if asset_id is None:
        raise DataSyncNotFoundError(
            "No local asset found for "
            f"sf_asset_id={sf_asset_id}"
        )

    return int(asset_id)


def build_failure_cause_operation_map(
    payload: dict,
) -> dict[int, list[int]]:
    """
    A CMMS asset_failure_causes válaszából
    elkészíti az alábbi leképezést:

        {
            asset_failurecause_id: operation_ids
        }

    Ezek az operation_ids értékek nem kerülnek
    az operations_done_lists táblába. Kizárólag
    a predikciós modul bemeneteként használjuk őket.
    """
    failure_causes = payload.get(
        "failure_causes"
    )

    if not isinstance(failure_causes, list):
        raise DataSyncValidationError(
            "failure_causes must be a list"
        )

    operation_map: dict[int, list[int]] = {}

    for failure_cause in failure_causes:
        if not isinstance(failure_cause, dict):
            raise DataSyncValidationError(
                "Every failure cause must be "
                "a JSON object"
            )

        asset_failurecause_id = (
            failure_cause.get(
                "asset_failurecause_id"
            )
        )

        if asset_failurecause_id is None:
            raise DataSyncValidationError(
                "asset_failurecause_id is missing"
            )

        normalized_asset_failurecause_id = int(
            asset_failurecause_id
        )

        if normalized_asset_failurecause_id <= 0:
            raise DataSyncValidationError(
                "asset_failurecause_id must be "
                "greater than zero"
            )

        if (
            normalized_asset_failurecause_id
            in operation_map
        ):
            raise DataSyncValidationError(
                "Duplicate asset_failurecause_id: "
                f"{normalized_asset_failurecause_id}"
            )

        operation_ids = failure_cause.get(
            "operation_ids"
        )

        if not isinstance(operation_ids, list):
            raise DataSyncValidationError(
                "operation_ids must be a list "
                "for asset_failurecause_id="
                f"{normalized_asset_failurecause_id}"
            )

        normalized_operation_ids: list[int] = []

        for operation_id in operation_ids:
            normalized_operation_id = int(
                operation_id
            )

            if normalized_operation_id <= 0:
                raise DataSyncValidationError(
                    "Every failure-cause operation_id "
                    "must be greater than zero"
                )

            normalized_operation_ids.append(
                normalized_operation_id
            )

        operation_map[
            normalized_asset_failurecause_id
        ] = normalized_operation_ids

    return operation_map


def select_failure_cause(
    payload: dict,
    failure_cause_id: int,
) -> dict:
    """
    Kiválasztja a CMMS-válaszból az incoming
    munkalap failure_cause_id értékéhez tartozó
    hibaokot.
    """
    failure_causes = payload.get(
        "failure_causes"
    )

    if not isinstance(failure_causes, list):
        raise DataSyncValidationError(
            "failure_causes must be a list"
        )

    for failure_cause in failure_causes:
        if not isinstance(failure_cause, dict):
            continue

        current_failure_cause_id = (
            failure_cause.get(
                "failure_cause_id"
            )
        )

        if current_failure_cause_id is None:
            continue

        if (
            int(current_failure_cause_id)
            == int(failure_cause_id)
        ):
            return failure_cause

    raise DataSyncNotFoundError(
        f"failure_cause_id={failure_cause_id} "
        "was not returned by the CMMS"
    )


def ensure_failure_type(
    session: Session,
    failure_cause: dict,
) -> int:
    """
    Létrehozza vagy frissíti a failure_types
    rekordot.

    Azonosító-leképezés:

        failure_type_id = failure_cause_id
    """
    failure_cause_id = failure_cause.get(
        "failure_cause_id"
    )

    if failure_cause_id is None:
        raise DataSyncValidationError(
            "failure_cause_id is missing"
        )

    failure_type_id = int(
        failure_cause_id
    )

    if failure_type_id <= 0:
        raise DataSyncValidationError(
            "failure_cause_id must be "
            "greater than zero"
        )

    failure_type_name = failure_cause.get(
        "code"
    )

    failure_type = session.get(
        FailureType,
        failure_type_id,
    )

    if failure_type is None:
        failure_type = FailureType(
            failure_type_id=failure_type_id,
            failure_type_name=(
                str(failure_type_name)
                if failure_type_name is not None
                else None
            ),
            is_preventive=None,
            failure_cause_id=failure_type_id,
        )

        session.add(failure_type)

    else:
        failure_type.failure_cause_id = (
            failure_type_id
        )

        if failure_type_name is not None:
            failure_type.failure_type_name = str(
                failure_type_name
            )

    session.flush()

    return failure_type_id


def ensure_asset_failure_type(
    session: Session,
    asset_id: int,
    failure_type_id: int,
    failure_cause: dict,
) -> int:
    """
    Létrehozza vagy frissíti az
    asset_failure_types rekordot.

    Azonosító-leképezés:

        asset_failure_type_id
            = asset_failurecause_id
    """
    asset_failurecause_id = (
        failure_cause.get(
            "asset_failurecause_id"
        )
    )

    if asset_failurecause_id is None:
        raise DataSyncValidationError(
            "asset_failurecause_id is missing"
        )

    asset_failure_type_id = int(
        asset_failurecause_id
    )

    if asset_failure_type_id <= 0:
        raise DataSyncValidationError(
            "asset_failurecause_id must be "
            "greater than zero"
        )

    asset_failure_type = session.get(
        AssetFailureType,
        asset_failure_type_id,
    )

    if asset_failure_type is None:
        asset_failure_type = AssetFailureType(
            asset_failure_type_id=(
                asset_failure_type_id
            ),
            asset_id=int(asset_id),
            failure_type_id=int(
                failure_type_id
            ),
            asset_failurecause_id=(
                asset_failure_type_id
            ),
        )

        session.add(asset_failure_type)

    else:
        if (
            int(asset_failure_type.asset_id)
            != int(asset_id)
        ):
            raise DataSyncValidationError(
                "The asset_failurecause_id is "
                "already assigned to another "
                "local asset"
            )

        asset_failure_type.failure_type_id = int(
            failure_type_id
        )

        asset_failure_type.asset_failurecause_id = (
            asset_failure_type_id
        )

    probability = failure_cause.get(
        "default_occurrence_probability"
    )

    if probability is not None:
        asset_failure_type.default_occurrence_probability = (
            float(probability)
        )
    else:
        asset_failure_type.default_occurrence_probability = (
            None
        )

    severity = failure_cause.get(
        "severity"
    )

    if severity is not None:
        asset_failure_type.severity = int(
            severity
        )
    else:
        asset_failure_type.severity = None

    session.flush()

    return asset_failure_type_id


def store_asset_worksheet(
    session: Session,
    workorder: AssetPredictIn,
    asset_id: int,
    asset_failure_type_id: int | None,
) -> AssetWorksheetList:
    """
    Létrehozza az asset_worksheet_lists rekordot.

    Leképezés:

        workorder.failuredate
            -> failure_start_time

        workorder.ended
            -> maintenance_end_date

        workorder.ended
            -> source_sys_time

        NULL
            -> downtime_in_min

    A sys_time értékét az adatbázis
    DEFAULT CURRENT_TIMESTAMP beállítása tölti ki.
    """
    worksheet = AssetWorksheetList(
        asset_id=int(asset_id),
        maintenance_end_date=(
            workorder.ended
        ),
        source_sys_time=workorder.ended,
        asset_failure_type_id=(
            asset_failure_type_id
        ),
        failure_start_time=(
            workorder.failuredate
        ),
        downtime_in_min=None,
    )

    session.add(worksheet)
    session.flush()

    return worksheet


def store_completed_operations(
    session: Session,
    operation_ids: list[int],
    worksheet: AssetWorksheetList,
) -> None:
    """
    Az /asset_predict üzenet operation_ids
    listájának minden eleméhez külön
    operations_done_lists rekordot készít.

    A CMMS asset_failure_causes válaszában
    szereplő operation_ids lista nem kerül
    ebbe a táblába.
    """
    for operation_id in operation_ids:
        normalized_operation_id = int(
            operation_id
        )

        if normalized_operation_id <= 0:
            raise DataSyncValidationError(
                "Every completed operation_id "
                "must be greater than zero"
            )

        operation = OperationsDoneList(
            operation_template_id=(
                normalized_operation_id
            ),
            asset_worksheet_list_id=int(
                worksheet.asset_worksheet_list_id
            ),
            maintenance_end_date=(
                worksheet.maintenance_end_date
            ),
        )

        session.add(operation)

    session.flush()


def synchronize_workorder(
    session: Session,
    workorder: AssetPredictIn,
) -> WorkorderSyncResult:
    """
    A teljes munkalap-szinkronizálási folyamat.

    Két külön operation_ids forrást kezel:

    1. workorder.operation_ids

       Ezek a ténylegesen elvégzett műveletek.
       Bekerülnek az operations_done_lists táblába.

    2. CMMS failure_causes[].operation_ids

       Ezek az egyes hibaokokhoz rendelt műveletek.
       Dictionary készül belőlük a predikció számára.

    A függvény nem végez commitot. A tranzakció
    véglegesítése a worker feladata.
    """
    workorder_type = (
        workorder.type.strip().upper()
    )

    # A CMMS-lekérés minden munkalapnál szükséges,
    # mert a failure_cause_operations dictionary
    # a predikció bemenete lesz.
    cmms_payload = asyncio.run(
        cmms_get_asset_failure_causes(
            workorder.sf_asset_id
        )
    )

    failure_cause_operations = (
        build_failure_cause_operation_map(
            cmms_payload
        )
    )

    failure_cause: dict | None = None

    if workorder_type != "PREVENTIVE":
        if workorder.failure_cause_id is None:
            raise DataSyncValidationError(
                "failure_cause_id is required "
                "for a non-preventive workorder"
            )

        failure_cause = select_failure_cause(
            cmms_payload,
            workorder.failure_cause_id,
        )

    # A külső SilverFrog assetazonosító
    # feloldása a belső asset_id értékre.
    asset_id = resolve_asset_id(
        session,
        workorder.sf_asset_id,
    )

    asset_failure_type_id: int | None = None

    # Preventív munkalapnál nem készül
    # failure_types vagy asset_failure_types rekord.
    if failure_cause is not None:
        failure_type_id = ensure_failure_type(
            session,
            failure_cause,
        )

        asset_failure_type_id = (
            ensure_asset_failure_type(
                session=session,
                asset_id=asset_id,
                failure_type_id=(
                    failure_type_id
                ),
                failure_cause=(
                    failure_cause
                ),
            )
        )

    worksheet = store_asset_worksheet(
        session=session,
        workorder=workorder,
        asset_id=asset_id,
        asset_failure_type_id=(
            asset_failure_type_id
        ),
    )

    # Kizárólag az /asset_predict
    # operation_ids listája kerül adatbázisba.
    store_completed_operations(
        session=session,
        operation_ids=(
            workorder.operation_ids
        ),
        worksheet=worksheet,
    )

    return WorkorderSyncResult(
        asset_id=asset_id,
        asset_failure_type_id=(
            asset_failure_type_id
        ),
        asset_worksheet_list_id=int(
            worksheet.asset_worksheet_list_id
        ),
        maintenance_end_date=(
            worksheet.maintenance_end_date
        ),
        failure_cause_operations=(
            failure_cause_operations
        ),
    )