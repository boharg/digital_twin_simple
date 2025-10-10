import hashlib, json, os, tempfile, shutil
from pathlib import Path
from datetime import datetime, date
import uuid


def request_sha256(payload: dict) -> str:
    def default(o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        raise TypeError(f"Type {type(o)} not serializable")

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=default).encode()
    return hashlib.sha256(raw).hexdigest()


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    # Add more types if needed (e.g., Path)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"Type {type(o)} not serializable")


def atomic_write_json(path: str, data: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(p.parent), encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, default=_json_default)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    shutil.move(tmp_path, p)  # Atomic on same filesystem
