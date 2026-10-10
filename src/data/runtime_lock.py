"""Hash-pinned materialization of the airline data tau2 needs at run time.

Running the official airline environment needs four files under
``TAU2_DATA_DIR/tau2/domains/airline/``: ``tasks.json``, ``split_tasks.json``,
``db.json`` and ``policy.md``. The first two are vendored byte-for-byte in this
repository; ``db.json`` (~7 MB) and ``policy.md`` are deliberately not committed
and must be copied from a local upstream checkout.

tau2 also reads the user-simulator guidelines from
``TAU2_DATA_DIR/tau2/user_simulator/``, so those are part of the same pinned set.
Every file is SHA256-pinned in ``configs/tau2.lock.json`` and re-hashed before
use, so a stale or tampered data directory can never be handed to tau2.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from airline_data.splits import (
    RUNTIME_HASHES,
    SNAPSHOT_HASHES,
    SPLIT_FILE,
    TASK_FILE,
    SplitValidationError,
    expected_upstream_lock,
    read_json,
)

_CHUNK = 1 << 20

# Vendored in this repository, so a local checkout is not needed for these.
VENDORED = (TASK_FILE, SPLIT_FILE)

# Everything tau2 must find under TAU2_DATA_DIR, with its pinned digest.
RUNTIME_FILES = {
    **{path: SNAPSHOT_HASHES[path] for path in VENDORED},
    **RUNTIME_HASHES,
}


class RuntimeDataError(SplitValidationError):
    """Runtime data is missing, tampered with, or the source is not pinned."""


def tau2_data_dir(root: Path | str) -> Path:
    """The directory to hand to tau2 as ``TAU2_DATA_DIR``."""
    return Path(root) / "data"


def _destination(root: Path, relative: str) -> Path:
    # Lock keys are already upstream-relative paths such as
    # "data/tau2/domains/airline/db.json", which is exactly where tau2 looks
    # them up once TAU2_DATA_DIR points at <root>/data.
    return Path(root) / relative


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(_CHUNK), b""):
                hasher.update(chunk)
    except OSError as exc:
        raise RuntimeDataError(f"Cannot read runtime data {path}: {exc}") from exc
    return hasher.hexdigest()


def _check_lock(root: Path) -> None:
    if read_json(Path(root) / "configs/tau2.lock.json") != expected_upstream_lock():
        raise RuntimeDataError("Upstream lock differs from pinned trust anchors")


def verify(root: Path | str) -> int:
    """Re-hash every materialized file; refuse on missing or changed bytes."""
    root = Path(root)
    _check_lock(root)
    for relative, expected in RUNTIME_FILES.items():
        path = _destination(root, relative)
        if not path.is_file():
            raise RuntimeDataError(f"Missing runtime data file: {path}")
        if _digest(path) != expected:
            raise RuntimeDataError(f"Runtime data SHA256 mismatch: {relative}")
    return len(RUNTIME_FILES)


def materialize(root: Path | str, upstream: Path | str) -> int:
    """Build ``<root>/data`` from the vendored anchor and a local upstream checkout.

    Both sources are hashed in full before anything is written, so a checkout that
    is not the pinned version never leaves a partially copied data directory.
    """
    root, upstream = Path(root), Path(upstream)
    _check_lock(root)
    sources = {
        relative: (
            root / "vendor/tau2" / relative
            if relative in VENDORED
            else upstream / relative
        )
        for relative in RUNTIME_FILES
    }
    for relative, origin in sources.items():
        if not origin.is_file():
            raise RuntimeDataError(f"Missing source file: {origin}")
        if _digest(origin) != RUNTIME_FILES[relative]:
            raise RuntimeDataError(
                f"Source SHA256 mismatch for {relative}: the source is not the "
                "pinned version"
            )
    for relative, origin in sources.items():
        destination = _destination(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    return verify(root)
