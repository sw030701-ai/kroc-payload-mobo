"""Fresh paired sensitivity followed by the selected 80-evaluation canonical run."""

import argparse
import shutil
from copy import deepcopy
from pathlib import Path

from kroc_mobo.analysis import make_analysis
from kroc_mobo.config import load_config
from kroc_mobo.experiments import run_exp1, run_exp2, run_pilot
from kroc_mobo.io import save_json
from kroc_mobo.sensitivity import analyze


def run(root):
    root = Path(root)
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    shutil.copytree("src", root / "source/src")
    shutil.copytree("configs", root / "source/configs")
    shutil.copy2(__file__, root / "source/run_budget80.py")
    c = load_config("configs/canonical_final.toml")
    c["mobo"]["n_evaluations"] = 80
    c["search"] = dict(kp=[0., 400.], ki=[0., 200.], kd=[0., 40.])
    save_json(root / "protocol.json", dict(
        evaluation_budget=80, initial=10, repeats=5, zero_anchor=True,
        current_upper=[400, 200, 40], expanded_upper=[800, 400, 80],
        decision="Expand if improvement in paired mean selection min JT >=5%; otherwise retain provisionally. Report observed saturation separately; never infer saturation from gain-bound attachment.",
        saturation="Voltage clipping fraction and maximum absolute current of selection CT; current is a feasibility constraint, not clipping.",
        independent_rerun="Both sensitivity arms and the selected canonical run are fresh runs; no transferred candidate inserted in local fronts.",
    ))
    for name, factor in (("current", 1), ("expanded", 2)):
        arm = deepcopy(c)
        arm["experiment"]["payloads"] = [1.0]
        arm["search"] = {k: [0., v[1] * factor] for k, v in c["search"].items()}
        run_exp1(arm, root / name)
    decision = analyze(root / "current", root / "expanded", root / "sensitivity", protocol="budget80")
    if decision["adopted"] == "expanded":
        c["search"] = {k: [0., v[1] * 2] for k, v in c["search"].items()}
    destination = root / "canonical"
    run_pilot(c, destination)
    run_exp1(c, destination)
    run_exp2(c, destination)
    make_analysis(destination)
    print("BUDGET80 COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    run(parser.parse_args().out)
