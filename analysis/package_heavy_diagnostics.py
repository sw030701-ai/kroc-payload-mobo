"""Archive completed supplementary diagnostics without replacing main results."""

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from kroc_mobo.heavy_diagnostics import sha
from kroc_mobo.io import require_complete, save_json


def package(root, report):
    root, report = Path(root), Path(report)
    require_complete(root, "heldout")
    if not json.loads((report / "AUDIT.json").read_text())["passed"]:
        raise ValueError("Audit must pass")
    target = report / "raw-results.zip"
    if target.exists():
        raise FileExistsError(target)
    scripts = root / "source/reporting"
    scripts.mkdir(exist_ok=True)
    for name in ("build_report.py", "report_heavy_diagnostics.py", "package_heavy_diagnostics.py"):
        shutil.copy2(Path("analysis") / name, scripts / name)
    shutil.copy2("docs/REVISION_HISTORY.md", root / "source/REVISION_HISTORY.md")
    files = [p for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
        and p.name != "RAW.sha256.json"]
    save_json(root / "RAW.sha256.json", {str(p.relative_to(root)): sha(p) for p in files})
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("README.txt", "Supplementary revision-4 diagnostics. Paths are repository-relative.\n"
            "Extract into the matching repository checkout. To reproduce/verify parent hashes, also extract\n"
            "the prior 80-evaluation raw-results.zip from reports/archive/canonical-final-20260927-budget80.\n"
            "mobo160 inherits the first 80 observations; so40 is warm-started with nominal CT.\n"
            "Both are supplementary, not replacements for the main 80-evaluation Experiment 1/2.\n"
            "Effective per-condition config, inherited hashes, seeds, manifests and frozen winners are included.\n"
            "source/src records the exact executed code; source/reporting records report/audit programs.\n")
        for p in files + [root / "RAW.sha256.json"]:
            archive.write(p, p.as_posix())
    if target.stat().st_size >= 100 * 1024**2:
        raise ValueError("Archive too large for a single GitHub file")
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
    save_json(report / "ARTIFACTS.sha256.json", {str(p.relative_to(report)): sha(p)
        for p in sorted(report.rglob("*")) if p.is_file() and p.name != "ARTIFACTS.sha256.json"})
    print(f"Verified raw archive: {target.stat().st_size / 1024**2:.2f} MiB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    package(args.root, args.report)
