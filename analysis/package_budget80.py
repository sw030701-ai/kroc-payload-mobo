"""Package complete raw results and hash every published artifact."""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from kroc_mobo.io import require_complete, save_json


def package(root, report):
    root, report = Path(root), Path(report)
    for arm in ("current", "expanded", "canonical"):
        require_complete(root / arm, "exp1")
    require_complete(root / "canonical", "exp2")
    audit = json.loads((report / "audit.json").read_text())
    if not audit["passed"]:
        raise ValueError("Audit must pass before packaging")
    target = report / "raw-results.zip"
    if target.exists():
        raise FileExistsError(target)
    reporting = root / "source/reporting"
    reporting.mkdir(exist_ok=True)
    for name in ("build_report.py", "report_budget80.py", "package_budget80.py"):
        shutil.copy2(Path("analysis") / name, reporting / name)
    shutil.copy2("docs/BUDGET80_PROTOCOL.md", root / "source/BUDGET80_PROTOCOL.md")
    save_json(root / "RAW.sha256.json", {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "RAW.sha256.json" and "__pycache__" not in path.parts
        and path.suffix not in (".pyc", ".nbc", ".nbi")
    })
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("README.txt", (
            "Raw 2026-09-27 bound/budget follow-up. Paths are relative to the repository root.\n"
            "Extract into the matching repository checkout. current/expanded are paired 1 kg sensitivity arms;\n"
            "canonical is the fresh selected-bound 1/2/3 kg run. All use 80 evaluations.\n"
            "source/src contains the exact execution code hashed in the run manifests.\n"
            "source/configs preserves pre-run configs; effective configs are each arm's config.json.\n"
            "protocol.json and source/run_budget80.py specify overrides and the decision rule.\n"
            "Source/reporting contains report/audit/packaging code; no Experiment 3.\n"
        ))
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".nbc", ".nbi"):
                archive.write(path, path.as_posix())
    if target.stat().st_size >= 100 * 1024**2:
        raise ValueError("Archive exceeds GitHub's single-file limit; split before publishing")
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity failure")
    save_json(report / "ARTIFACTS.sha256.json", {
        str(path.relative_to(report)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(report.rglob("*"))
        if path.is_file() and path.name != "ARTIFACTS.sha256.json"
    })
    print(f"Packaged {target.stat().st_size / 1024**2:.2f} MiB; ZIP integrity verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    package(args.root, args.report)
