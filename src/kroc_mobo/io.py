"""Run manifests, atomic tabular checkpoints, and immutable configuration snapshots."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

from .config import fingerprint


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temp.replace(path)


def save_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(temp, index=False)
    temp.replace(path)


def initialize_run(root, c, stage):
    root = Path(root)
    snapshot = root / "config.json"
    if snapshot.exists():
        old = json.loads(snapshot.read_text())
        if fingerprint(old) != fingerprint(c):
            raise ValueError("Output directory uses a different config; select a new --out directory")
    else:
        save_json(snapshot, c)
    manifest_path = root / stage / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"{stage} already exists; use a new --out directory (no silent overwrite)")
    packages = {}
    for package in ["numpy", "scipy", "pandas", "matplotlib", "torch", "botorch", "gpytorch"]:
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = "not installed"
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parents[2],
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision = "uncommitted"
    manifest = dict(
        stage=stage,
        status="running",
        started_utc=datetime.now(timezone.utc).isoformat(),
        config_sha256=fingerprint(c),
        parameter_status=c["metadata"]["parameter_status"],
        python=platform.python_version(),
        platform=platform.platform(),
        packages=packages,
        git_revision=revision,
        source_sha256={
            str(path.relative_to(Path(__file__).resolve().parents[2])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(Path(__file__).resolve().parent.glob("*.py"))
        },
    )
    save_json(manifest_path, manifest)
    return manifest


def finish_run(root, stage, manifest, **extra):
    manifest.update(status="completed", finished_utc=datetime.now(timezone.utc).isoformat(), **extra)
    save_json(Path(root) / stage / "manifest.json", manifest)


def load_snapshot(root):
    return json.loads((Path(root) / "config.json").read_text())


def require_complete(root, stage):
    path = Path(root) / stage / "manifest.json"
    if not path.exists() or json.loads(path.read_text())["status"] != "completed":
        raise ValueError(f"{stage} must finish before the next stage")
