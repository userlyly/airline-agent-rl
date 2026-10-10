from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from airline_data.runtime_lock import (
    RUNTIME_FILES,
    RuntimeDataError,
    materialize,
    tau2_data_dir,
    verify,
)
from airline_data.splits import RUNTIME_HASHES, SNAPSHOT_HASHES

RELATIVE = "data/tau2/domains/airline/policy.md"
CONTENT = b"# synthetic policy standing in for the pinned bytes\n"

UPSTREAM = Path(__file__).resolve().parents[1].parent / "tau2-bench"
needs_upstream = pytest.mark.skipif(
    not (UPSTREAM / "data/tau2/domains/airline/db.json").is_file(),
    reason="local tau2-bench checkout not available",
)


@pytest.fixture
def synthetic(monkeypatch: pytest.MonkeyPatch, copied_root: Path) -> tuple[Path, Path]:
    """A root with the real lock but a one-file, test-sized pinned digest."""
    monkeypatch.setattr(
        "airline_data.runtime_lock.RUNTIME_FILES",
        {RELATIVE: hashlib.sha256(CONTENT).hexdigest()},
    )
    source = copied_root / "upstream"
    (source / Path(RELATIVE).parent).mkdir(parents=True)
    (source / RELATIVE).write_bytes(CONTENT)
    return copied_root, source


def test_lock_pins_every_runtime_file(root: Path) -> None:
    lock = json.loads((root / "configs/tau2.lock.json").read_text(encoding="utf-8"))
    assert set(RUNTIME_FILES) == {
        "data/tau2/domains/airline/tasks.json",
        "data/tau2/domains/airline/split_tasks.json",
        "data/tau2/domains/airline/db.json",
        "data/tau2/domains/airline/policy.md",
        "data/tau2/user_simulator/simulation_guidelines.md",
        "data/tau2/user_simulator/simulation_guidelines_tools.md",
        "data/tau2/user_simulator/simulation_guidelines_voice.md",
        "data/tau2/user_simulator/simulation_guidelines_voice_tools.md",
    }
    for path, digest in RUNTIME_FILES.items():
        section = "files" if path in SNAPSHOT_HASHES else "runtime_files"
        assert lock[section][path]["sha256"] == digest
    # The bulk/runtime-only files are hash-pinned but must never be vendored.
    assert len(SNAPSHOT_HASHES) == 3
    assert len(RUNTIME_HASHES) == 6
    for relative in RUNTIME_FILES:
        if relative not in SNAPSHOT_HASHES:
            assert not (root / "vendor/tau2" / relative).exists()


def test_tau2_data_dir_points_at_ignored_tree(root: Path) -> None:
    assert tau2_data_dir(root) == root / "data"


def test_materialize_then_verify(synthetic: tuple[Path, Path]) -> None:
    root, source = synthetic
    assert materialize(root, source) == 1
    assert (root / RELATIVE).read_bytes() == CONTENT
    assert verify(root) == 1


def test_tampered_destination_refused(synthetic: tuple[Path, Path]) -> None:
    root, source = synthetic
    materialize(root, source)
    destination = root / RELATIVE
    destination.write_bytes(destination.read_bytes() + b"\n")
    with pytest.raises(RuntimeDataError, match="SHA256 mismatch"):
        verify(root)


def test_missing_destination_refused(synthetic: tuple[Path, Path]) -> None:
    root, _ = synthetic
    with pytest.raises(RuntimeDataError, match="Missing runtime data file"):
        verify(root)


def test_unpinned_source_refused_without_partial_copy(
    synthetic: tuple[Path, Path],
) -> None:
    root, source = synthetic
    (source / RELATIVE).write_bytes(b"# a different policy\n")
    with pytest.raises(RuntimeDataError, match="Source SHA256 mismatch"):
        materialize(root, source)
    assert not (root / RELATIVE).exists()


def test_missing_source_refused(synthetic: tuple[Path, Path]) -> None:
    root, source = synthetic
    (source / RELATIVE).unlink()
    with pytest.raises(RuntimeDataError, match="Missing source file"):
        materialize(root, source)


def test_forged_lock_refused(synthetic: tuple[Path, Path]) -> None:
    root, source = synthetic
    lock_file = root / "configs/tau2.lock.json"
    lock = json.loads(lock_file.read_text(encoding="utf-8"))
    lock["runtime_files"]["data/tau2/domains/airline/policy.md"]["sha256"] = "0" * 64
    lock_file.write_text(json.dumps(lock), encoding="utf-8")
    for call in (lambda: verify(root), lambda: materialize(root, source)):
        with pytest.raises(RuntimeDataError, match="trust anchors"):
            call()


@needs_upstream
def test_pinned_upstream_materializes(copied_root: Path) -> None:
    assert materialize(copied_root, UPSTREAM) == len(RUNTIME_FILES)
    for relative in RUNTIME_FILES:
        assert (copied_root / relative).is_file()


def test_prepare_cli_refuses_unpinned_source(root: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty-upstream"
    empty.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/eval/prepare_data.py"),
            "--root",
            str(root),
            "--source",
            str(empty),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Runtime data check failed" in result.stderr


@needs_upstream
def test_prepare_cli_materializes(copied_root: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/prepare_data.py"),
            "--root",
            str(copied_root),
            "--source",
            str(UPSTREAM),
        ],
        cwd=copied_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["runtime_files_verified"] == len(RUNTIME_FILES)
