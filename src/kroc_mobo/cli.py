"""Command-line entry point."""

import argparse

from .config import load_config
from .io import load_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description="PLACEHOLDER / illustrative KRoC experiment pipeline")
    parser.add_argument("command", choices=["pilot", "exp1", "exp2", "plot", "all"])
    parser.add_argument("--config", default="configs/illustrative.toml")
    parser.add_argument("--out", default="results/illustrative")
    parser.add_argument(
        "--smoke", action="store_true", help="Reduce BO budget and repetitions, keep 5 s model"
    )
    parser.add_argument("--backend", choices=["qnehvi", "qlognehvi", "sobol"])
    args = parser.parse_args(argv)
    if args.command in ("exp2", "plot"):
        if args.smoke or args.backend:
            parser.error("exp2/plot read frozen config from --out; omit --smoke and --backend")
        c = load_snapshot(args.out)
    else:
        c = load_config(args.config, smoke=args.smoke)
        if args.backend:
            c["mobo"]["backend"] = args.backend
    print(c["metadata"]["parameter_status"], flush=True)
    from .experiments import run_exp1, run_exp2, run_pilot

    if args.command in ("pilot", "all"):
        run_pilot(c, args.out)
    if args.command in ("exp1", "all"):
        run_exp1(c, args.out)
    if args.command in ("exp2", "all"):
        run_exp2(c, args.out)
    if args.command in ("plot", "all"):
        from .analysis import make_analysis

        make_analysis(args.out)


if __name__ == "__main__":
    main()
