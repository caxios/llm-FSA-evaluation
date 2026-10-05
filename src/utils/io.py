"""Raw-data storage. Everything under data/raw/ is written once, with a metadata sidecar."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Query/header names that carry credentials and must never be written to disk.
SECRET_KEYS = {"crtfc_key", "auth_key", "api_key", "apikey", "key", "authorization", "token"}
REDACTED = "<redacted>"


def redact(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    return {k: (REDACTED if k.lower() in SECRET_KEYS else v) for k, v in params.items()}


def atomic_write(path: Path, data: bytes) -> None:
    """Write `data` to `path` via a temp file + rename, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def meta_path(path: Path) -> Path:
    return path.with_name(path.name + ".meta.json")


def write_raw(
    path: Path,
    payload: bytes | str | dict | list,
    *,
    url: str,
    params: dict[str, Any] | None = None,
    status: str | int | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Store a raw API response exactly as received, plus `<name>.meta.json`."""
    if isinstance(payload, (dict, list)):
        data = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = payload
    atomic_write(path, data)
    meta = {
        "url": url,
        "params": redact(params),
        "status": status,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "bytes": len(data),
        **(extra or {}),
    }
    atomic_write(meta_path(path), json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    return path


def read_raw(path: Path) -> tuple[bytes, dict[str, Any]]:
    """Return (payload bytes, metadata)."""
    meta = json.loads(meta_path(path).read_text(encoding="utf-8"))
    return path.read_bytes(), meta


def read_raw_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
