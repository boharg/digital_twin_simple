import hashlib, json, os, tempfile, shutil
from pathlib import Path


def request_sha256(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def atomic_write_json(path: str, data: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(p.parent)) as tmp:
        json.dump(data, tmp, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    shutil.move(tmp_path, p)  # POSIX atomic
