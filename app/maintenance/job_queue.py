from contextlib import contextmanager
from threading import Event, Thread

from loguru import logger
from sqlalchemy import func, text, update
from sqlalchemy.orm import Session

from ..db import SyncSessionLocal
from ..models import (
    JobStatus,
    PredictionJob,
)


# A heartbeat 30 másodpercenként jelzi, hogy
# a job feldolgozása még folyamatban van.
JOB_HEARTBEAT_INTERVAL_SEC = 30


# Csak akkor tekintünk egy processing jobot
# beragadtnak, ha 10 perce nem érkezett heartbeat.
STUCK_JOB_MAX_AGE_SEC = 600


def _is_admin_shutdown_error(
    exc: Exception,
) -> bool:
    """
    Felismeri azt a PostgreSQL-hibát, amikor
    az adatbázis-kapcsolat adminisztrátori
    leállítás miatt szakad meg.
    """

    return (
        "terminating connection due to "
        "administrator command"
        in str(exc).lower()
    )


@contextmanager
def session_scope():
    """
    Rövid életű szinkron adatbázis-sessiont
    biztosít.

    Siker esetén commitol, hiba esetén
    rollbacket végez.
    """

    session: Session = SyncSessionLocal()

    try:
        yield session
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def requeue_stuck_jobs(
    session: Session,
) -> int:
    """
    Újra queued állapotba teszi azokat a
    processing jobokat, amelyek updated_at
    mezője a megengedett időnél régebbi.

    Visszaadja az újra sorba állított jobok
    számát.
    """

    result = session.execute(
        text(
            """
            UPDATE prediction_jobs
            SET status = 'queued',
                error_message = 'Automatically requeued: heartbeat timeout',
                updated_at = NOW()
            WHERE status = 'processing'
              AND updated_at
                  < NOW()
                    - (
                        INTERVAL '1 second'
                        * :max_age
                    )
            """
        ),
        {
            "max_age": (
                STUCK_JOB_MAX_AGE_SEC
            )
        },
    )

    session.commit()

    requeued_count = int(
        result.rowcount or 0
    )

    if requeued_count > 0:
        logger.warning(
            "Automatically requeued {} "
            "stuck prediction job(s).",
            requeued_count,
        )

    return requeued_count


def claim_one_job(
    session: Session,
) -> PredictionJob | None:
    """
    Lefoglalja a legrégebbi queued jobot.

    A FOR UPDATE SKIP LOCKED miatt több worker
    is működhet párhuzamosan anélkül, hogy
    ugyanazt a jobot egyszerre lefoglalnák.
    """

    row = session.execute(
        text(
            """
            SELECT job_id
            FROM prediction_jobs
            WHERE status = 'queued'
            ORDER BY created_at, job_id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
    ).first()

    if row is None:
        return None

    job_id = int(
        row[0]
    )

    job = session.get(
        PredictionJob,
        job_id,
    )

    if job is None:
        return None

    job.status = JobStatus.processing
    job.error_message = None

    # A claim időpontját adatbázis-idővel
    # állítjuk be.
    session.flush()

    session.execute(update(PredictionJob).where(PredictionJob.job_id == job_id).values(updated_at=func.now()))

    session.commit()
    session.refresh(
        job
    )

    return job


def touch_processing_job(
    job_id: int,
) -> bool:
    """
    Frissíti egy processing állapotú job
    updated_at mezőjét.

    Minden heartbeat saját adatbázis-sessiont
    használ, ezért nem használja a worker
    feldolgozási sessionjét másik szálból.

    True:
        a job még processing állapotú volt,
        és a heartbeat sikeresen frissítette.

    False:
        a job már nincs processing állapotban,
        vagy nem található.
    """

    with session_scope() as session:
        result = session.execute(update(PredictionJob).where(PredictionJob.job_id == int(job_id), PredictionJob.status == JobStatus.processing).values(updated_at=func.now()))

        return bool(
            result.rowcount
        )


class JobHeartbeat:
    """
    Háttérszálon életben tart egy processing
    állapotú prediction jobot.
    """

    def __init__(
        self,
        job_id: int,
        interval_sec: int = (
            JOB_HEARTBEAT_INTERVAL_SEC
        ),
    ):
        self.job_id = int(
            job_id
        )

        self.interval_sec = int(
            interval_sec
        )

        self._stop_event = Event()

        self._thread = Thread(
            target=self._run,
            name=(
                "prediction-job-heartbeat-"
                f"{self.job_id}"
            ),
            daemon=True,
        )

    def start(self) -> None:
        """
        Azonnal küld egy heartbeatet, majd
        elindítja a háttérszálat.
        """

        try:
            is_processing = (
                touch_processing_job(
                    self.job_id
                )
            )

            if not is_processing:
                logger.warning(
                    "Heartbeat was not started "
                    "because job_id={} is not "
                    "in processing state.",
                    self.job_id,
                )
                return

        except Exception as error:
            logger.exception(
                "Initial heartbeat failed for "
                "job_id={}: {}",
                self.job_id,
                error,
            )

        self._thread.start()

    def stop(self) -> None:
        """
        Leállítja a heartbeat háttérszálat.
        """

        self._stop_event.set()

        if self._thread.is_alive():
            self._thread.join(
                timeout=(self.interval_sec + 5)
            )

    def _run(self) -> None:
        """
        A heartbeat háttérszál ciklusa.
        """

        while not self._stop_event.wait(
            self.interval_sec
        ):
            try:
                is_processing = (
                    touch_processing_job(
                        self.job_id
                    )
                )

                if not is_processing:
                    # A job már done, error,
                    # not_found vagy queued lett.
                    # Nincs szükség további
                    # heartbeat küldésére.
                    return

                logger.debug(
                    "Heartbeat updated for "
                    "job_id={}.",
                    self.job_id,
                )

            except Exception as error:
                # Egy sikertelen heartbeat miatt
                # nem állítjuk le rögtön a workert.
                # A következő intervallumban újra
                # megpróbáljuk.
                logger.exception(
                    "Heartbeat failed for "
                    "job_id={}: {}",
                    self.job_id,
                    error,
                )


@contextmanager
def job_heartbeat(
    job_id: int,
):
    """
    Context managerként indítja és állítja le
    a job heartbeatjét.

    Használat:

        with job_heartbeat(job_id):
            process_job(...)
    """

    heartbeat = JobHeartbeat(
        job_id=job_id
    )

    heartbeat.start()

    try:
        yield heartbeat

    finally:
        heartbeat.stop()
