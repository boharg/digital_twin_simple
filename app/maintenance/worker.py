import asyncio
import time
from datetime import datetime

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..data_sync import (
    DataSyncNotFoundError,
    DataSyncValidationError,
    synchronize_workorder,
)
from ..models import (
    JobStatus,
    Prediction,
    PredictionJob,
)
from ..schemas import (
    AssetFailureCausePredictionPayload,
    AssetPredictionPayload,
    AssetPredictIn,
    FailureCausePredictionItem,
)
from .cmms import (
    cmms_post_asset_failure_cause_prediction,
    cmms_post_asset_prediction,
)
from .job_queue import (
    _is_admin_shutdown_error,
    claim_one_job,
    requeue_stuck_jobs,
    session_scope,
)
from .predict import predict


POLL_INTERVAL_SEC = 1.0
REQUEUE_INTERVAL_SEC = 30.0


def update_job_status(
    session: Session,
    job_id: int,
    status: JobStatus,
    error_message: str | None = None,
) -> None:
    job = session.get(
        PredictionJob,
        int(job_id),
    )

    if job is None:
        return

    job.status = status
    job.error_message = error_message
    job.updated_at = datetime.utcnow()

    session.commit()


def validate_probability(
    value: object,
    field_name: str,
) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be numeric"
        ) from error

    if not 0.0 <= probability <= 1.0:
        raise ValueError(
            f"{field_name} must be between 0 and 1"
        )

    return probability


def validate_prediction_result(
    prediction_result: object,
    known_asset_failurecause_ids: set[int],
) -> tuple[int, list[int], list[float], float]:
    if not isinstance(
        prediction_result,
        dict,
    ):
        raise ValueError(
            "predict() must return a dictionary"
        )

    prediction_id_raw = prediction_result.get(
        "prediction_id"
    )

    if prediction_id_raw is None:
        raise ValueError(
            "prediction_id is missing from "
            "the prediction result"
        )

    prediction_id = int(
        prediction_id_raw
    )

    if prediction_id <= 0:
        raise ValueError(
            "prediction_id must be greater than zero"
        )

    failure_type_ids_raw = prediction_result.get(
        "failure_type_ids"
    )

    if not isinstance(
        failure_type_ids_raw,
        list,
    ):
        raise ValueError(
            "failure_type_ids must be a list"
        )

    failure_type_probability_raw = (
        prediction_result.get(
            "failure_type_probability"
        )
    )

    if not isinstance(
        failure_type_probability_raw,
        list,
    ):
        raise ValueError(
            "failure_type_probability must be a list"
        )

    if (
        len(failure_type_ids_raw)
        != len(failure_type_probability_raw)
    ):
        raise ValueError(
            "failure_type_ids and "
            "failure_type_probability must have "
            "the same number of elements"
        )

    failure_type_ids: list[int] = []
    failure_type_probabilities: list[float] = []

    for failure_type_id_raw in failure_type_ids_raw:
        failure_type_id = int(
            failure_type_id_raw
        )

        if failure_type_id <= 0:
            raise ValueError(
                "Every failure_type_id must be "
                "greater than zero"
            )

        if (
            failure_type_id
            not in known_asset_failurecause_ids
        ):
            raise ValueError(
                "The prediction returned an unknown "
                "asset_failurecause_id: "
                f"{failure_type_id}"
            )

        failure_type_ids.append(
            failure_type_id
        )

    if (
        len(failure_type_ids)
        != len(set(failure_type_ids))
    ):
        raise ValueError(
            "failure_type_ids contains duplicates"
        )

    for index, probability_raw in enumerate(
        failure_type_probability_raw
    ):
        failure_type_probabilities.append(
            validate_probability(
                probability_raw,
                (
                    "failure_type_probability"
                    f"[{index}]"
                ),
            )
        )

    predicted_reliability = (
        validate_probability(
            prediction_result.get(
                "predicted_reliability"
            ),
            "predicted_reliability",
        )
    )

    return (
        prediction_id,
        failure_type_ids,
        failure_type_probabilities,
        predicted_reliability,
    )


def store_prediction(
    session: Session,
    prediction_id: int,
    job_id: int,
    asset_id: int,
    asset_failure_type_id: int | None,
) -> Prediction:
    existing_prediction = session.get(
        Prediction,
        int(prediction_id),
    )

    if existing_prediction is not None:
        if (
            int(existing_prediction.job_id)
            != int(job_id)
        ):
            raise ValueError(
                "prediction_id is already assigned "
                "to another job"
            )

        existing_prediction.asset_id = int(
            asset_id
        )

        existing_prediction.asset_failure_type_id = (
            int(asset_failure_type_id)
            if asset_failure_type_id is not None
            else None
        )

        session.flush()

        return existing_prediction

    prediction = Prediction(
        prediction_id=int(prediction_id),
        asset_id=int(asset_id),
        asset_failure_type_id=(
            int(asset_failure_type_id)
            if asset_failure_type_id is not None
            else None
        ),
        job_id=int(job_id),
    )

    session.add(prediction)
    session.flush()

    return prediction


def build_failure_cause_items(
    failure_type_ids: list[int],
    failure_type_probabilities: list[float],
) -> list[FailureCausePredictionItem]:
    failure_causes: list[
        FailureCausePredictionItem
    ] = []

    for (
        failure_type_id,
        probability,
    ) in zip(
        failure_type_ids,
        failure_type_probabilities,
    ):
        failure_causes.append(
            FailureCausePredictionItem(
                # A predikció failure_type_ids
                # listájában ebben a folyamatban az
                # asset_failurecause_id értékek vannak.
                asset_failurecause_id=(
                    failure_type_id
                ),
                predicted_reliability=(
                    probability
                ),
            )
        )

    if not failure_causes:
        raise ValueError(
            "The prediction returned no "
            "failure-cause results"
        )

    return failure_causes


def process_job(
    session: Session,
    job: PredictionJob,
) -> None:
    job_id = int(
        job.job_id
    )

    if job.endpoint_type != "asset_predict":
        update_job_status(
            session=session,
            job_id=job_id,
            status=JobStatus.error,
            error_message=(
                "Unsupported endpoint_type: "
                f"{job.endpoint_type}"
            ),
        )
        return

    try:
        workorder = AssetPredictIn.model_validate(
            job.payload
        )

    except ValidationError as error:
        update_job_status(
            session=session,
            job_id=job_id,
            status=JobStatus.error,
            error_message=(
                "Payload validation failed: "
                f"{error}"
            ),
        )
        return

    try:
        sync_result = synchronize_workorder(
            session=session,
            workorder=workorder,
        )

        prediction_result = predict(
            job_id=job_id,
            maintenance_end_time=(
                workorder.ended
            ),
            failure_start_time=(
                workorder.failuredate
            ),
            asset_id=(
                sync_result.asset_id
            ),
            failure_cause_operations=(
                sync_result.failure_cause_operations
            ),
        )

        (
            prediction_id,
            failure_type_ids,
            failure_type_probabilities,
            predicted_reliability,
        ) = validate_prediction_result(
            prediction_result=(
                prediction_result
            ),
            known_asset_failurecause_ids=set(
                sync_result
                .failure_cause_operations
                .keys()
            ),
        )

        store_prediction(
            session=session,
            prediction_id=prediction_id,
            job_id=job_id,
            asset_id=(
                sync_result.asset_id
            ),
            asset_failure_type_id=(
                sync_result
                .asset_failure_type_id
            ),
        )

        asset_prediction_payload = (
            AssetPredictionPayload(
                prediction_id=prediction_id,

                # A CMMS felé a külső azonosítót
                # asset_id néven küldjük vissza.
                sf_asset_id=(
                    workorder.sf_asset_id
                ),

                predicted_reliability=(
                    predicted_reliability
                ),
            )
        )

        failure_cause_payload = (
            AssetFailureCausePredictionPayload(
                prediction_id=prediction_id,
                failure_causes=(
                    build_failure_cause_items(
                        failure_type_ids=(
                            failure_type_ids
                        ),
                        failure_type_probabilities=(
                            failure_type_probabilities
                        ),
                    )
                ),
            )
        )

        # Egy tranzakcióban kerül mentésre:
        # - failure_types
        # - asset_failure_types
        # - asset_worksheet_lists
        # - operations_done_lists
        # - predictions
        session.commit()

    except DataSyncNotFoundError as error:
        session.rollback()

        update_job_status(
            session=session,
            job_id=job_id,
            status=JobStatus.not_found,
            error_message=str(error),
        )
        return

    except (
        DataSyncValidationError,
        ValueError,
        TypeError,
    ) as error:
        session.rollback()

        update_job_status(
            session=session,
            job_id=job_id,
            status=JobStatus.error,
            error_message=str(error),
        )
        return

    try:
        asset_response = asyncio.run(
            cmms_post_asset_prediction(
                asset_prediction_payload.model_dump(
                    mode="json",
                    by_alias=True,
                )
            )
        )

        logger.info(
            "CMMS asset prediction response: {}",
            asset_response,
        )

        failure_cause_response = asyncio.run(
            cmms_post_asset_failure_cause_prediction(
                failure_cause_payload.model_dump(
                    mode="json",
                )
            )
        )

        logger.info(
            "CMMS failure-cause prediction "
            "response: {}",
            failure_cause_response,
        )

    except Exception as error:
        update_job_status(
            session=session,
            job_id=job_id,
            status=JobStatus.error,
            error_message=(
                "CMMS prediction POST failed: "
                f"{error}"
            ),
        )
        return

    update_job_status(
        session=session,
        job_id=job_id,
        status=JobStatus.done,
        error_message=None,
    )

    logger.info(
        "Prediction job completed: "
        "job_id={}, prediction_id={}",
        job_id,
        prediction_id,
    )


def main() -> None:
    logger.info(
        "DB queue worker started."
    )

    last_requeue = 0.0

    while True:
        try:
            now = time.monotonic()

            if (
                now - last_requeue
                >= REQUEUE_INTERVAL_SEC
            ):
                with session_scope() as session:
                    requeue_stuck_jobs(
                        session
                    )

                last_requeue = now

            with session_scope() as session:
                claimed_job = claim_one_job(
                    session
                )

                job_id = (
                    int(claimed_job.job_id)
                    if claimed_job is not None
                    else None
                )

            if job_id is None:
                time.sleep(
                    POLL_INTERVAL_SEC
                )
                continue

            with session_scope() as session:
                job = session.get(
                    PredictionJob,
                    job_id,
                )

                if job is None:
                    continue

                try:
                    process_job(
                        session=session,
                        job=job,
                    )

                except Exception as error:
                    logger.exception(
                        "Unhandled process-job error: {}",
                        error,
                    )

                    with session_scope() as (
                        recovery_session
                    ):
                        recovery_job = (
                            recovery_session.get(
                                PredictionJob,
                                job_id,
                            )
                        )

                        if recovery_job is None:
                            continue

                        if _is_admin_shutdown_error(
                            error
                        ):
                            recovery_job.status = (
                                JobStatus.queued
                            )
                            recovery_job.error_message = (
                                "Retry: database "
                                "connection terminated"
                            )
                        else:
                            recovery_job.status = (
                                JobStatus.error
                            )
                            recovery_job.error_message = (
                                "Unhandled error: "
                                f"{error}"
                            )

                        recovery_job.updated_at = (
                            datetime.utcnow()
                        )

        except Exception as error:
            logger.exception(
                "Worker loop error: {}",
                error,
            )

            time.sleep(
                POLL_INTERVAL_SEC
            )


if __name__ == "__main__":
    main()