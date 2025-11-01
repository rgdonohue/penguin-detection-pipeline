from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_git_sha() -> str | None:
    # Avoid shelling out; allow env override if CI sets it
    return os.environ.get("GIT_SHA") or None


def write_provenance(out_dir: Path, filename: str = "provenance.json", extra: Dict[str, Any] | None = None) -> None:
    """Write a lightweight provenance record to `out_dir/filename`.

    Includes timestamp, Python version, platform, optional GIT_SHA env var,
    and any extra fields provided by the caller (e.g., inputs, params).
    Safe no-op if directory is not writeable.
    """
    try:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "timestamp": _now_iso(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "git_sha": _safe_git_sha(),
        }
        if extra:
            payload.update(extra)
        (out_dir / filename).write_text(json.dumps(payload, indent=2))
    except Exception:
        # Non-fatal; provenance should never break pipelines
        pass


def append_timings(
    out_dir: Path,
    *,
    component: str,
    timings: Dict[str, Any],
    extra: Dict[str, Any] | None = None,
    filename: str = "timings.json",
) -> None:
    """Append a timing record to a JSON list under out_dir/filename.

    The file will contain a JSON array of entries of the form:
      {"timestamp": <ISO>, "component": "lidar", "timings": {...}, **extra}

    This is best-effort and will never raise; if the file is malformed it will be overwritten.
    """
    try:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        data: list[dict] = []
        if path.exists():
            try:
                cur = json.loads(path.read_text())
                if isinstance(cur, list):
                    data = cur
            except Exception:
                # Malformed → overwrite with a fresh list
                data = []
        entry: Dict[str, Any] = {
            "timestamp": _now_iso(),
            "component": component,
            "timings": timings,
        }
        if extra:
            entry.update(extra)
        data.append(entry)
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        # Non-fatal; timing capture should not break pipelines
        pass
