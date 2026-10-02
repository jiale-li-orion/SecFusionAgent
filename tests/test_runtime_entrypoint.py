from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "deploy/runtime-entrypoint.sh"


def _run_entrypoint(artifact_root: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "SECFUSION_ARTIFACT_STORE_BACKEND": "filesystem",
        "SECFUSION_ARTIFACT_ROOT": str(artifact_root),
        "SECFUSION_S3_BUCKET": "evidence",
    }
    return subprocess.run(
        [str(ENTRYPOINT), "sh", "-c", "printf runtime-started"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_runtime_entrypoint_probes_real_artifact_hash_directory(tmp_path: Path) -> None:
    result = _run_entrypoint(tmp_path)
    assert result.returncode == 0
    assert result.stdout == "runtime-started"
    assert (tmp_path / "evidence/sha256").is_dir()
    assert not list((tmp_path / "evidence/sha256").glob(".runtime-write-probe.*"))


def test_runtime_entrypoint_fails_before_process_when_hash_directory_is_not_writable(
    tmp_path: Path,
) -> None:
    probe_dir = tmp_path / "evidence/sha256"
    probe_dir.mkdir(parents=True)
    probe_dir.chmod(0o555)
    try:
        result = _run_entrypoint(tmp_path)
    finally:
        probe_dir.chmod(0o755)

    assert result.returncode != 0
    assert "runtime-started" not in result.stdout
    assert "artifact store is not writable" in result.stderr
