from ..db import SyncSessionLocal
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..models import PredictionJob, JobStatus

STUCK_JOB_MAX_AGE_SEC = 120


def _is_admin_shutdown_error(exc: Exception) -> bool:
    return "terminating connection due to administrator command" in str(exc)


@contextmanager
def session_scope():
    session: Session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def requeue_stuck_jobs(session: Session):
    session.execute(
        text("""
        UPDATE prediction_jobs
        SET status = 'queued',
            updated_at = NOW()
        WHERE status = 'processing'
          AND updated_at < NOW() - (INTERVAL '1 second' * :max_age)
        """),
        {"max_age": STUCK_JOB_MAX_AGE_SEC}
    )
    session.commit()


def claim_one_job(session: Session) -> PredictionJob | None:
    row = session.execute(
        text("""
        SELECT job_id
        FROM prediction_jobs
        WHERE status = 'queued'
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """)
    ).first()
    if not row:
        return None
    job = session.get(PredictionJob, row[0])
    job.status = JobStatus.processing
    session.commit()
    session.refresh(job)
    return job
